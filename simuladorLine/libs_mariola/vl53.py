import time
from smbus2 import SMBus


class VL53L0X:  # noqa
    VL53L0X_I2C_ADDR = 0x29
    VL53L0X_DEFAULT_ADDR = 0x29
    VL53L0X_ALT_ADDR = 0x30
    MUX_ADDR = 0x70
    I2C_BUS = 1

    # Timeouts padrão (ms)
    TIMEOUT_CALIBRATION_MS = 1000
    TIMEOUT_RANGING_MS = 500
    TIMEOUT_SPAD_MS = 500

    def __init__(self, porta_mux=None):
        if porta_mux is None or porta_mux > 7 or porta_mux < 0:
            raise ValueError('Canal inválido (deve ser 0 a 7)')

        self.porta_mux = porta_mux
        self.stop_variable = 0
        self.measurement_timing_budget_us = 0
        self.did_timeout = False
        self.bus = SMBus(self.I2C_BUS)

        self.select_channel()

        # Aborta qualquer medição em andamento antes de inicializar
        self._abort_ranging()

        # Descobre em qual endereço o sensor já está
        self.VL53L0X_I2C_ADDR = self._detect_address()

        # Muda para endereço alternativo se ainda estiver no padrão
        if self.VL53L0X_I2C_ADDR == self.VL53L0X_DEFAULT_ADDR:
            self.set_i2c_address(self.VL53L0X_ALT_ADDR)

        self._init_sensor()

    # ------------------------------------------------------------------
    # Seleção de canal do mux
    # ------------------------------------------------------------------

    def select_channel(self):
        self.bus.write_byte(self.MUX_ADDR, 1 << self.porta_mux)
        time.sleep(0.005)

    def close_channel(self):
        self.bus.write_byte(self.MUX_ADDR, 0x00)
        time.sleep(0.005)

    # ------------------------------------------------------------------
    # Recuperação de bus stuck no segmento downstream
    # ------------------------------------------------------------------

    def recover(self):
        """
        Fecha o canal do mux e reabre — libera o segmento downstream
        sem precisar do pino XSHUT. Após recuperação reinicializa o sensor.
        """
        print(f'[VL53L0X] Recuperando sensor no canal {self.porta_mux}...')
        try:
            self.close_channel()
            time.sleep(0.1)
            self.select_channel()
            time.sleep(0.5)  # VL53L0X precisa de tempo pra reinicializar
            self._abort_ranging()
            self._init_sensor()
            print(f'[VL53L0X] Canal {self.porta_mux} recuperado com sucesso.')
        except OSError as e:
            raise OSError(f'[VL53L0X] Falha na recuperação do canal {self.porta_mux}: {e}')

    # ------------------------------------------------------------------
    # Detecção de endereço
    # ------------------------------------------------------------------

    def _detect_address(self):
        """Verifica em qual endereço o sensor está respondendo."""
        for addr in (self.VL53L0X_ALT_ADDR, self.VL53L0X_DEFAULT_ADDR):
            try:
                self.VL53L0X_I2C_ADDR = addr
                self.read_byte(0x00)
                print(f'[VL53L0X] Sensor encontrado no endereço 0x{addr:02X}')
                return addr
            except OSError:
                pass
        raise OSError('[VL53L0X] Sensor não encontrado em nenhum endereço conhecido')

    # ------------------------------------------------------------------
    # Abort de medição em andamento
    # ------------------------------------------------------------------

    def _abort_ranging(self):
        """Para qualquer medição em andamento e limpa a interrupção."""
        try:
            self.write_byte(0x00, 0x00)  # SYSRANGE_START — para medição
            self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        except OSError:
            pass  # Se o sensor não responde, ignora — recover() cuidará disso

    # ------------------------------------------------------------------
    # Inicialização completa do sensor
    # ------------------------------------------------------------------

    def _init_sensor(self):
        # Configuração inicial
        self.write_byte(0x88, 0x00)
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.stop_variable = self.read_byte(0x91)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        # Desabilitar verificações de limite de sinal
        msrc_config_control = self.read_byte(0x60)
        self.write_byte(0x60, msrc_config_control | 0x12)

        # Configurar limite de taxa de sinal final para 0.25 MCPS
        self.set_signal_rate_limit(0.25)

        self.write_byte(0x01, 0xFF)  # SYSTEM_SEQUENCE_CONFIG

        # Inicialização estática
        spad_count, spad_type_is_aperture = self.get_spad_info()
        ref_spad_map = list(self.read_multi(0xB0, 6))

        self.write_byte(0xFF, 0x01)
        self.write_byte(0x4F, 0x00)
        self.write_byte(0x4E, 0x2C)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0xB6, 0xB4)

        first_spad_to_enable = 12 if spad_type_is_aperture else 0
        spads_enabled = 0

        for i in range(48):
            if i < first_spad_to_enable or spads_enabled == spad_count:
                ref_spad_map[i // 8] &= ~(1 << (i % 8))
            elif (ref_spad_map[i // 8] >> (i % 8)) & 0x1:
                spads_enabled += 1

        self.write_multi(0xB0, ref_spad_map, 6)

        self.load_tuning_settings()

        # Configurar interrupção
        self.write_byte(0x0A, 0x04)
        gpio_hv_mux_active_high = self.read_byte(0x84)
        self.write_byte(0x84, gpio_hv_mux_active_high & ~0x10)
        self.write_byte(0x0B, 0x01)

        measurement_timing_budget_us = self.get_measurement_timing_budget()
        self.write_byte(0x01, 0xE8)
        self.set_measurement_timing_budget(measurement_timing_budget_us)

        self.perform_ref_calibration()

    # ------------------------------------------------------------------
    # Polling com timeout — substitui todos os "while ... pass"
    # ------------------------------------------------------------------

    def _wait_for_bit(self, reg, mask, expected=0, timeout_ms=500):
        """
        Aguarda até que (read_byte(reg) & mask) != expected.
        Lança TimeoutError se o tempo limite for atingido.
        """
        deadline = time.monotonic() + timeout_ms / 1000
        while (self.read_byte(reg) & mask) == expected:
            if time.monotonic() > deadline:
                self.did_timeout = True
                raise TimeoutError(
                    f'[VL53L0X] Timeout aguardando reg=0x{reg:02X} '
                    f'mask=0x{mask:02X} (canal {self.porta_mux})'
                )
            time.sleep(0.001)

    # ------------------------------------------------------------------
    # I2C: leitura e escrita
    # ------------------------------------------------------------------

    def write_byte(self, reg, value):
        self.bus.write_byte_data(self.VL53L0X_I2C_ADDR, reg, value)

    def read_byte(self, reg):
        return self.bus.read_byte_data(self.VL53L0X_I2C_ADDR, reg)

    def read_multi(self, reg, length):
        return self.bus.read_i2c_block_data(self.VL53L0X_I2C_ADDR, reg, length)

    def write_multi(self, reg, data, length):
        self.bus.write_i2c_block_data(self.VL53L0X_I2C_ADDR, reg, list(data[:length]))

    def read_word(self, reg):
        high = self.read_byte(reg)
        low = self.read_byte(reg + 1)
        return (high << 8) | low

    def write_word(self, reg, value):
        self.write_byte(reg, (value >> 8) & 0xFF)
        self.write_byte(reg + 1, value & 0xFF)

    # ------------------------------------------------------------------
    # Configuração de endereço I2C
    # ------------------------------------------------------------------

    def set_i2c_address(self, new_address):
        if new_address < 0x08 or new_address > 0x77:
            raise ValueError('Endereço I2C inválido (deve ser entre 0x08 e 0x77)')
        self.write_byte(0x8A, new_address)
        self.VL53L0X_I2C_ADDR = new_address

    # ------------------------------------------------------------------
    # Configuração de taxa de sinal
    # ------------------------------------------------------------------

    def set_signal_rate_limit(self, limit):
        value = int(limit * (1 << 7))
        self.write_byte(0x44, (value >> 8) & 0xFF)
        self.write_byte(0x45, value & 0xFF)

    # ------------------------------------------------------------------
    # SPAD info
    # ------------------------------------------------------------------

    def get_spad_info(self):
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0xFF, 0x06)
        self.write_byte(0x83, self.read_byte(0x83) | 0x04)
        self.write_byte(0xFF, 0x07)
        self.write_byte(0x81, 0x01)
        self.write_byte(0x80, 0x01)
        self.write_byte(0x94, 0x6B)
        self.write_byte(0x83, 0x00)

        # Aguarda com timeout em vez de loop infinito
        self._wait_for_bit(0x83, 0xFF, expected=0x00, timeout_ms=self.TIMEOUT_SPAD_MS)

        self.write_byte(0x83, 0x01)
        tmp = self.read_byte(0x92)

        spad_count = tmp & 0x7F
        spad_type_is_aperture = bool((tmp >> 7) & 0x01)

        self.write_byte(0x81, 0x00)
        self.write_byte(0xFF, 0x06)
        self.write_byte(0x83, self.read_byte(0x83) & ~0x04)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        return spad_count, spad_type_is_aperture

    # ------------------------------------------------------------------
    # Tuning settings
    # ------------------------------------------------------------------

    def load_tuning_settings(self):
        tuning_settings = [
            (0xFF, 0x01), (0x00, 0x00), (0xFF, 0x00), (0x09, 0x00),
            (0x10, 0x00), (0x11, 0x00), (0x24, 0x01), (0x25, 0xFF),
            (0x75, 0x00), (0xFF, 0x01), (0x4E, 0x2C), (0x48, 0x00),
            (0x30, 0x20), (0xFF, 0x00), (0x30, 0x09), (0x54, 0x00),
            (0x31, 0x04), (0x32, 0x03), (0x40, 0x83), (0x46, 0x25),
            (0x60, 0x00), (0x27, 0x00), (0x50, 0x06), (0x51, 0x00),
            (0x52, 0x96), (0x56, 0x08), (0x57, 0x30), (0x61, 0x00),
            (0x62, 0x00), (0x64, 0x00), (0x65, 0x00), (0x66, 0xA0),
            (0xFF, 0x01), (0x22, 0x32), (0x47, 0x14), (0x49, 0xFF),
            (0x4A, 0x00), (0xFF, 0x00), (0x7A, 0x0A), (0x7B, 0x00),
            (0x78, 0x21), (0xFF, 0x01), (0x23, 0x34), (0x42, 0x00),
            (0x44, 0xFF), (0x45, 0x26), (0x46, 0x05), (0x40, 0x40),
            (0x0E, 0x06), (0x20, 0x1A), (0x43, 0x40), (0xFF, 0x00),
            (0x34, 0x03), (0x35, 0x44), (0xFF, 0x01), (0x31, 0x04),
            (0x4B, 0x09), (0x4C, 0x05), (0x4D, 0x04), (0xFF, 0x00),
            (0x44, 0x00), (0x45, 0x20), (0x47, 0x08), (0x48, 0x28),
            (0x67, 0x00), (0x70, 0x04), (0x71, 0x01), (0x72, 0xFE),
            (0x76, 0x00), (0x77, 0x00), (0xFF, 0x01), (0x0D, 0x01),
            (0xFF, 0x00), (0x80, 0x01), (0x01, 0xF8), (0xFF, 0x01),
            (0x8E, 0x01), (0x00, 0x01), (0xFF, 0x00), (0x80, 0x00),
        ]
        for reg, value in tuning_settings:
            self.write_byte(reg, value)

    # ------------------------------------------------------------------
    # Calibração de referência
    # ------------------------------------------------------------------

    def perform_ref_calibration(self):
        self.write_byte(0x01, 0x01)
        if not self.perform_single_ref_calibration(0x40):
            raise Exception('[VL53L0X] Erro na calibração VHV')
        self.write_byte(0x01, 0x02)
        if not self.perform_single_ref_calibration(0x00):
            raise Exception('[VL53L0X] Erro na calibração de fase')
        self.write_byte(0x01, 0xE8)

    def perform_single_ref_calibration(self, vhv_init_byte):
        self.write_byte(0x00, 0x01 | vhv_init_byte)  # SYSRANGE_START

        # Aguarda interrupção com timeout
        self._wait_for_bit(0x13, 0x07, expected=0x00, timeout_ms=self.TIMEOUT_CALIBRATION_MS)

        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        self.write_byte(0x00, 0x00)  # SYSRANGE_START
        return True

    # ------------------------------------------------------------------
    # Timing budget
    # ------------------------------------------------------------------

    def get_measurement_timing_budget(self):
        StartOverhead = 1910
        EndOverhead = 960
        MsrcOverhead = 660
        TccOverhead = 590
        DssOverhead = 690
        PreRangeOverhead = 660
        FinalRangeOverhead = 550

        budget_us = StartOverhead + EndOverhead
        enables = self.get_sequence_step_enables()
        timeouts = self.get_sequence_step_timeouts(enables)

        if enables['tcc']:
            budget_us += timeouts['msrc_dss_tcc_us'] + TccOverhead
        if enables['dss']:
            budget_us += 2 * (timeouts['msrc_dss_tcc_us'] + DssOverhead)
        elif enables['msrc']:
            budget_us += timeouts['msrc_dss_tcc_us'] + MsrcOverhead
        if enables['pre_range']:
            budget_us += timeouts['pre_range_us'] + PreRangeOverhead
        if enables['final_range']:
            budget_us += timeouts['final_range_us'] + FinalRangeOverhead

        self.measurement_timing_budget_us = budget_us
        return budget_us

    def set_measurement_timing_budget(self, budget_us):
        StartOverhead = 1910
        EndOverhead = 960
        MsrcOverhead = 660
        TccOverhead = 590
        DssOverhead = 690
        PreRangeOverhead = 660
        FinalRangeOverhead = 550

        used_budget_us = StartOverhead + EndOverhead
        enables = self.get_sequence_step_enables()
        timeouts = self.get_sequence_step_timeouts(enables)

        if enables['tcc']:
            used_budget_us += timeouts['msrc_dss_tcc_us'] + TccOverhead
        if enables['dss']:
            used_budget_us += 2 * (timeouts['msrc_dss_tcc_us'] + DssOverhead)
        elif enables['msrc']:
            used_budget_us += timeouts['msrc_dss_tcc_us'] + MsrcOverhead
        if enables['pre_range']:
            used_budget_us += timeouts['pre_range_us'] + PreRangeOverhead
        if enables['final_range']:
            used_budget_us += FinalRangeOverhead
            if used_budget_us > budget_us:
                return False
            final_range_timeout_us = budget_us - used_budget_us
            final_range_timeout_mclks = self.timeout_microseconds_to_mclks(
                final_range_timeout_us,
                timeouts['final_range_vcsel_period_pclks'],
            )
            if enables['pre_range']:
                final_range_timeout_mclks += timeouts['pre_range_mclks']
            self.write_word(0x71, self.encode_timeout(final_range_timeout_mclks))

        self.measurement_timing_budget_us = budget_us
        return True

    def get_sequence_step_enables(self):
        sequence_config = self.read_byte(0x01)
        return {
            'tcc': (sequence_config >> 4) & 0x1,
            'dss': (sequence_config >> 3) & 0x1,
            'msrc': (sequence_config >> 2) & 0x1,
            'pre_range': (sequence_config >> 6) & 0x1,
            'final_range': (sequence_config >> 7) & 0x1,
        }

    def get_sequence_step_timeouts(self, enables):
        timeouts = {}
        timeouts['pre_range_vcsel_period_pclks'] = self.get_vcsel_pulse_period('pre_range')
        timeouts['msrc_dss_tcc_mclks'] = self.read_byte(0x46) + 1
        timeouts['msrc_dss_tcc_us'] = self.timeout_mclks_to_microseconds(
            timeouts['msrc_dss_tcc_mclks'],
            timeouts['pre_range_vcsel_period_pclks'],
        )
        timeouts['pre_range_mclks'] = self.decode_timeout(self.read_word(0x51))
        timeouts['pre_range_us'] = self.timeout_mclks_to_microseconds(
            timeouts['pre_range_mclks'],
            timeouts['pre_range_vcsel_period_pclks'],
        )
        timeouts['final_range_vcsel_period_pclks'] = self.get_vcsel_pulse_period('final_range')
        timeouts['final_range_mclks'] = self.decode_timeout(self.read_word(0x71))
        if enables['pre_range']:
            timeouts['final_range_mclks'] -= timeouts['pre_range_mclks']
        timeouts['final_range_us'] = self.timeout_mclks_to_microseconds(
            timeouts['final_range_mclks'],
            timeouts['final_range_vcsel_period_pclks'],
        )
        return timeouts

    def get_vcsel_pulse_period(self, type_):
        if type_ == 'pre_range':
            return self.decode_vcsel_period(self.read_byte(0x50))
        elif type_ == 'final_range':
            return self.decode_vcsel_period(self.read_byte(0x70))
        else:
            raise ValueError('Tipo inválido para VCSEL pulse period')

    def decode_vcsel_period(self, reg_val):
        return ((reg_val) + 1) << 1

    def decode_timeout(self, reg_val):
        return ((reg_val & 0xFF) << ((reg_val >> 8) & 0xFF)) + 1

    def timeout_mclks_to_microseconds(self, timeout_period_mclks, vcsel_period_pclks):
        macro_period_ns = self.calc_macro_period(vcsel_period_pclks)
        return ((timeout_period_mclks * macro_period_ns) + 500) // 1000

    def timeout_microseconds_to_mclks(self, timeout_period_us, vcsel_period_pclks):
        macro_period_ns = self.calc_macro_period(vcsel_period_pclks)
        return ((timeout_period_us * 1000) + (macro_period_ns // 2)) // macro_period_ns

    def calc_macro_period(self, vcsel_period_pclks):
        return ((2304 * vcsel_period_pclks * 1655) + 500) // 1000

    def encode_timeout(self, timeout_mclks):
        ls_byte = 0
        ms_byte = 0
        if timeout_mclks > 0:
            ls_byte = timeout_mclks - 1
            while (ls_byte & 0xFFFFFF00) > 0:
                ls_byte >>= 1
                ms_byte += 1
            return (ms_byte << 8) | (ls_byte & 0xFF)
        return 0

    # ------------------------------------------------------------------
    # Medição contínua
    # ------------------------------------------------------------------

    def start_continuous(self, period_ms=0):
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.stop_variable)  # usa stop_variable salvo no __init__
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        if period_ms != 0:
            osc_calibrate_val = self.read_word(0xF8)
            if osc_calibrate_val != 0:
                period_ms *= osc_calibrate_val
            self.write_multi(0x04, list(period_ms.to_bytes(4, 'big')), 4)
            self.write_byte(0x00, 0x04)  # modo cronometrado
        else:
            self.write_byte(0x00, 0x02)  # modo back-to-back

    def stop_continuous(self):
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, 0x00)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)

    # ------------------------------------------------------------------
    # Leitura de distância
    # ------------------------------------------------------------------

    def read_range_continuous_millimeters(self):
        self.select_channel()
        # Aguarda resultado com timeout — não trava mais em loop infinito
        self._wait_for_bit(0x13, 0x07, expected=0x00, timeout_ms=self.TIMEOUT_RANGING_MS)
        range_mm = self.read_word(0x14 + 10)  # RESULT_RANGE_STATUS + 10
        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        return range_mm

    def read_range_single_millimeters(self):
        self.select_channel()
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.stop_variable)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)
        self.write_byte(0x00, 0x01)  # SYSRANGE_START single-shot

        # Aguarda início com timeout
        self._wait_for_bit(0x00, 0x01, expected=0x01, timeout_ms=self.TIMEOUT_RANGING_MS)

        return self.read_range_continuous_millimeters()

    def solicita_leitura(self):
        """Inicia uma medição single-shot sem bloquear aguardando o resultado."""
        self.select_channel()
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.stop_variable)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)
        self.write_byte(0x00, 0x01)  # SYSRANGE_START single-shot

        # Aguarda disparo com timeout
        self._wait_for_bit(0x00, 0x01, expected=0x01, timeout_ms=self.TIMEOUT_RANGING_MS)

    def leitura_mm(self):
        """Lê o resultado de uma medição já solicitada via solicita_leitura()."""
        self.select_channel()
        self._wait_for_bit(0x13, 0x07, expected=0x00, timeout_ms=self.TIMEOUT_RANGING_MS)
        range_mm = self.read_word(0x14 + 10)
        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        return range_mm

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def timeout_occurred(self):
        tmp = self.did_timeout
        self.did_timeout = False
        return tmp