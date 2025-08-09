from smbus2 import SMBus


class VL53L0X:  # noqa
    VL53L0X_I2C_ADDR = 0x29  # Endereço padrão
    MUX_ADDR = 0x70  # Endereço do TCA9548A
    bus = None
    I2C_BUS = 1  # Verifique qual /dev/i2c-X você está usando
    stop_variable = 0

    def __init__(self, porta_mux=None):
        self.bus = self.bus = SMBus(self.I2C_BUS)
        self.porta_mux = porta_mux
        if self.porta_mux > 7 or self.porta_mux < 0:
            raise ValueError('Canal inválido (deve ser 0 a 7)')
        self.select_channel()
        self.select_channel()
        model_id = self.read_byte(0xC0)
        if model_id != 0xEE:
            print('Retorno do ID do sensor: ', hex(model_id))
            # raise Exception("VL53L0X não encontrado no endereço 0x29")
            print('VL53L0X nao encontrado no endereço 0x29')

        # Configuração inicial do sensor
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
        ref_spad_map = self.read_multi(0xB0, 6)  # GLOBAL_CONFIG_SPAD_ENABLES_REF_0

        self.write_byte(0xFF, 0x01)
        self.write_byte(0x4F, 0x00)  # DYNAMIC_SPAD_REF_EN_START_OFFSET
        self.write_byte(0x4E, 0x2C)  # DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD
        self.write_byte(0xFF, 0x00)
        self.write_byte(0xB6, 0xB4)  # GLOBAL_CONFIG_REF_EN_START_SELECT

        first_spad_to_enable = 12 if spad_type_is_aperture else 0
        spads_enabled = 0

        for i in range(48):
            if i < first_spad_to_enable or spads_enabled == spad_count:
                ref_spad_map[i // 8] &= ~(1 << (i % 8))
            elif (ref_spad_map[i // 8] >> (i % 8)) & 0x1:
                spads_enabled += 1

        self.write_multi(0xB0, ref_spad_map, 6)  # GLOBAL_CONFIG_SPAD_ENABLES_REF_0

        # Carregar configurações de ajuste padrão
        self.load_tuning_settings()

        # Configurar interrupção para "novo amostra pronta"
        self.write_byte(0x0A, 0x04)  # SYSTEM_INTERRUPT_CONFIG_GPIO
        gpio_hv_mux_active_high = self.read_byte(0x84)
        self.write_byte(0x84, gpio_hv_mux_active_high & ~0x10)  # GPIO_HV_MUX_ACTIVE_HIGH
        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR

        # Configurar sequência e orçamento de tempo
        measurement_timing_budget_us = self.get_measurement_timing_budget()

        self.write_byte(0x01, 0xE8)  # SYSTEM_SEQUENCE_CONFIG

        self.set_measurement_timing_budget(measurement_timing_budget_us)

        # Calibração de referência
        self.perform_ref_calibration()

    def select_channel(self):
        self.bus.write_byte(self.MUX_ADDR, 1 << self.porta_mux)

    def write_byte(self, reg, value):
        self.bus.write_byte_data(self.VL53L0X_I2C_ADDR, reg, value)

    def read_byte(self, reg):
        return self.bus.read_byte_data(self.VL53L0X_I2C_ADDR, reg)

    def read_multi(self, reg, length):
        return self.bus.read_i2c_block_data(self.VL53L0X_I2C_ADDR, reg, length)

    def write_multi(self, reg, data, length):
        self.bus.write_i2c_block_data(self.VL53L0X_I2C_ADDR, reg, data[:length])

    def set_signal_rate_limit(self, limit):
        # Configurar limite de taxa de sinal
        value = int(limit * (1 << 7))
        self.write_byte(0x44, (value >> 8) & 0xFF)
        self.write_byte(0x45, value & 0xFF)

    def get_spad_info(self):
        # Obter informações sobre SPADs
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

        # Esperar até que o registro 0x83 seja diferente de 0
        while self.read_byte(0x83) == 0x00:
            pass

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

    def load_tuning_settings(self):
        # Carregar configurações de ajuste padrão
        tuning_settings = [(0xFF, 0x01), (0x00, 0x00), (0xFF, 0x00), (0x09, 0x00), (0x10, 0x00), (0x11, 0x00), (0x24, 0x01), (0x25, 0xFF), (0x75, 0x00), (0xFF, 0x01), (0x4E, 0x2C), (0x48, 0x00), (0x30, 0x20), (0xFF, 0x00), (0x30, 0x09), (0x54, 0x00), (0x31, 0x04), (0x32, 0x03), (0x40, 0x83), (0x46, 0x25), (0x60, 0x00), (0x27, 0x00), (0x50, 0x06), (0x51, 0x00), (0x52, 0x96), (0x56, 0x08), (0x57, 0x30), (0x61, 0x00), (0x62, 0x00), (0x64, 0x00), (0x65, 0x00), (0x66, 0xA0), (0xFF, 0x01), (0x22, 0x32), (0x47, 0x14), (0x49, 0xFF), (0x4A, 0x00), (0xFF, 0x00), (0x7A, 0x0A), (0x7B, 0x00), (0x78, 0x21), (0xFF, 0x01), (0x23, 0x34), (0x42, 0x00), (0x44, 0xFF), (0x45, 0x26), (0x46, 0x05), (0x40, 0x40), (0x0E, 0x06), (0x20, 0x1A), (0x43, 0x40), (0xFF, 0x00), (0x34, 0x03), (0x35, 0x44), (0xFF, 0x01), (0x31, 0x04), (0x4B, 0x09), (0x4C, 0x05), (0x4D, 0x04), (0xFF, 0x00), (0x44, 0x00), (0x45, 0x20), (0x47, 0x08), (0x48, 0x28), (0x67, 0x00), (0x70, 0x04), (0x71, 0x01), (0x72, 0xFE), (0x76, 0x00), (0x77, 0x00), (0xFF, 0x01), (0x0D, 0x01), (0xFF, 0x00), (0x80, 0x01), (0x01, 0xF8), (0xFF, 0x01), (0x8E, 0x01), (0x00, 0x01), (0xFF, 0x00), (0x80, 0x00)]  # fmt: skip
        for reg, value in tuning_settings:
            self.write_byte(reg, value)

    def perform_ref_calibration(self):
        # Calibração de referência
        self.write_byte(0x01, 0x01)  # SYSTEM_SEQUENCE_CONFIG
        if not self.perform_single_ref_calibration(0x40):
            raise Exception('Erro na calibração de referência VHV')
        self.write_byte(0x01, 0x02)  # SYSTEM_SEQUENCE_CONFIG
        if not self.perform_single_ref_calibration(0x00):
            raise Exception('Erro na calibração de fase')
        self.write_byte(0x01, 0xE8)  # Restaurar configuração de sequência

    def perform_single_ref_calibration(self, vhv_init_byte):
        # Baseado em VL53L0X_perform_single_ref_calibration
        self.write_byte(0x00, 0x01 | vhv_init_byte)  # SYSRANGE_START (VL53L0X_REG_SYSRANGE_MODE_START_STOP)

        # Simular início do timeout
        while (self.read_byte(0x13) & 0x07) == 0:  # RESULT_INTERRUPT_STATUS
            pass  # Esperar até que o bit de interrupção seja definido

        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        self.write_byte(0x00, 0x00)  # SYSRANGE_START

        return True

    def get_measurement_timing_budget(self):
        # Constantes de overhead
        StartOverhead = 1910
        EndOverhead = 960
        MsrcOverhead = 660
        TccOverhead = 590
        DssOverhead = 690
        PreRangeOverhead = 660
        FinalRangeOverhead = 550

        # "Start and end overhead times always present"
        budget_us = StartOverhead + EndOverhead

        # Obter habilitações e tempos de sequência
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

        self.measurement_timing_budget_us = budget_us  # Armazenar para reutilização interna
        return budget_us

    def set_measurement_timing_budget(self, budget_us):
        # Configurar o orçamento de tempo de medição
        StartOverhead = 1910
        EndOverhead = 960
        MsrcOverhead = 660
        TccOverhead = 590
        DssOverhead = 690
        PreRangeOverhead = 660
        FinalRangeOverhead = 550

        used_budget_us = StartOverhead + EndOverhead

        # Obter habilitações e tempos de sequência
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

            # Verificar se há espaço suficiente para o timeout final
            if used_budget_us > budget_us:
                # "Timeout solicitado muito grande."
                return False

            final_range_timeout_us = budget_us - used_budget_us

            # Converter timeout final para MCLKs
            final_range_timeout_mclks = self.timeout_microseconds_to_mclks(
                final_range_timeout_us,
                timeouts['final_range_vcsel_period_pclks'],
            )

            if enables['pre_range']:
                final_range_timeout_mclks += timeouts['pre_range_mclks']

            # Configurar o timeout final
            self.write_word(
                0x71, self.encode_timeout(final_range_timeout_mclks)
            )  # FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI

        self.measurement_timing_budget_us = budget_us  # Armazenar para reutilização interna
        return True

    def get_sequence_step_enables(self):
        # Obter habilitações de etapas de sequência
        sequence_config = self.read_byte(0x01)  # SYSTEM_SEQUENCE_CONFIG
        return {
            'tcc': (sequence_config >> 4) & 0x1,
            'dss': (sequence_config >> 3) & 0x1,
            'msrc': (sequence_config >> 2) & 0x1,
            'pre_range': (sequence_config >> 6) & 0x1,
            'final_range': (sequence_config >> 7) & 0x1,
        }

    def timeout_microseconds_to_mclks(self, timeout_period_us, vcsel_period_pclks):
        # Converter timeout de microsegundos para MCLKs
        macro_period_ns = self.calc_macro_period(vcsel_period_pclks)
        return ((timeout_period_us * 1000) + (macro_period_ns // 2)) // macro_period_ns

    def get_sequence_step_timeouts(self, enables):
        # Obter tempos de etapas de sequência
        timeouts = {}
        timeouts['pre_range_vcsel_period_pclks'] = self.get_vcsel_pulse_period('pre_range')

        timeouts['msrc_dss_tcc_mclks'] = self.read_byte(0x46) + 1  # MSRC_CONFIG_TIMEOUT_MACROP
        timeouts['msrc_dss_tcc_us'] = self.timeout_mclks_to_microseconds(
            timeouts['msrc_dss_tcc_mclks'],
            timeouts['pre_range_vcsel_period_pclks'],
        )

        timeouts['pre_range_mclks'] = self.decode_timeout(
            self.read_word(0x51)
        )  # PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI
        timeouts['pre_range_us'] = self.timeout_mclks_to_microseconds(
            timeouts['pre_range_mclks'],
            timeouts['pre_range_vcsel_period_pclks'],
        )

        timeouts['final_range_vcsel_period_pclks'] = self.get_vcsel_pulse_period('final_range')

        timeouts['final_range_mclks'] = self.decode_timeout(
            self.read_word(0x71)
        )  # FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI
        if enables['pre_range']:
            timeouts['final_range_mclks'] -= timeouts['pre_range_mclks']
        timeouts['final_range_us'] = self.timeout_mclks_to_microseconds(
            timeouts['final_range_mclks'],
            timeouts['final_range_vcsel_period_pclks'],
        )

        return timeouts

    def get_vcsel_pulse_period(self, type_):
        # Obter período de pulso VCSEL
        if type_ == 'pre_range':
            return self.decode_vcsel_period(self.read_byte(0x50))  # PRE_RANGE_CONFIG_VCSEL_PERIOD
        elif type_ == 'final_range':
            return self.decode_vcsel_period(self.read_byte(0x70))  # FINAL_RANGE_CONFIG_VCSEL_PERIOD
        else:
            raise ValueError('Tipo inválido para VCSEL pulse period')

    def decode_vcsel_period(self, reg_val):
        # Decodificar período VCSEL
        return ((reg_val) + 1) << 1

    def decode_timeout(self, reg_val):
        # Decodificar timeout
        return ((reg_val & 0xFF) << ((reg_val >> 8) & 0xFF)) + 1

    def timeout_mclks_to_microseconds(self, timeout_period_mclks, vcsel_period_pclks):
        # Converter timeout de MCLKs para microsegundos
        macro_period_ns = self.calc_macro_period(vcsel_period_pclks)
        return ((timeout_period_mclks * macro_period_ns) + 500) // 1000

    def calc_macro_period(self, vcsel_period_pclks):
        # Calcular período macro em nanosegundos
        return ((2304 * vcsel_period_pclks * 1655) + 500) // 1000

    def read_word(self, reg):
        # Ler um registro de 16 bits
        high_byte = self.read_byte(reg)
        low_byte = self.read_byte(reg + 1)
        return (high_byte << 8) | low_byte

    def start_continuous(self, period_ms=0):
        # Iniciar medições contínuas
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.read_byte(0x91))  # stop_variable
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        if period_ms != 0:
            # Modo contínuo cronometrado
            osc_calibrate_val = self.read_word(0xF8)  # OSC_CALIBRATE_VAL
            if osc_calibrate_val != 0:
                period_ms *= osc_calibrate_val
            self.write_multi(0x04, period_ms.to_bytes(4, 'big'), 4)  # SYSTEM_INTERMEASUREMENT_PERIOD
            self.write_byte(0x00, 0x04)  # SYSRANGE_START (modo cronometrado)
        else:
            # Modo contínuo back-to-back
            self.write_byte(0x00, 0x02)  # SYSRANGE_START (modo back-to-back)

    def stop_continuous(self):
        # Parar medições contínuas
        self.write_byte(0x00, 0x01)  # SYSRANGE_START (modo single-shot)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, 0x00)
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)

    def read_range_continuous_millimeters(self):
        self.select_channel()
        self.select_channel()
        # Ler distância em milímetros no modo contínuo
        while (self.read_byte(0x13) & 0x07) == 0:  # RESULT_INTERRUPT_STATUS
            pass  # Esperar até que o resultado esteja pronto

        range_mm = self.read_word(0x14 + 10)  # RESULT_RANGE_STATUS + 10
        self.write_byte(0x0B, 0x01)  # SYSTEM_INTERRUPT_CLEAR
        return range_mm

    def read_range_single_millimeters(self):
        self.select_channel()
        self.select_channel()
        # Realizar uma medição única e retornar a distância em milímetros
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.stop_variable)  # stop_variable
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        self.write_byte(0x00, 0x01)  # SYSRANGE_START (modo single-shot)

        # Esperar até que o bit de início seja limpo
        while self.read_byte(0x00) & 0x01:  # SYSRANGE_START
            pass

        return self.read_range_continuous_millimeters()

    def solicita_leitura(self):
        self.select_channel()
        self.select_channel()
        # Realizar uma medição única e retornar a distância em milímetros
        self.write_byte(0x80, 0x01)
        self.write_byte(0xFF, 0x01)
        self.write_byte(0x00, 0x00)
        self.write_byte(0x91, self.stop_variable)  # stop_variable
        self.write_byte(0x00, 0x01)
        self.write_byte(0xFF, 0x00)
        self.write_byte(0x80, 0x00)

        self.write_byte(0x00, 0x01)  # SYSRANGE_START (modo single-shot)

        # Esperar até que o bit de início seja limpo
        while self.read_byte(0x00) & 0x01:  # SYSRANGE_START
            pass

    def timeout_occurred(self):
        # Verificar se ocorreu um timeout
        tmp = self.did_timeout
        self.did_timeout = False
        return tmp

    def write_word(self, reg, value):
        # Escrever um valor de 16 bits (word) em um registro
        high_byte = (value >> 8) & 0xFF  # Byte mais significativo
        low_byte = value & 0xFF  # Byte menos significativo
        self.write_byte(reg, high_byte)
        self.write_byte(reg + 1, low_byte)

    def encode_timeout(self, timeout_mclks):
        # Formato: "(LSByte * 2^MSByte) + 1"
        ls_byte = 0
        ms_byte = 0

        if timeout_mclks > 0:
            ls_byte = timeout_mclks - 1

            while (ls_byte & 0xFFFFFF00) > 0:
                ls_byte >>= 1
                ms_byte += 1

            return (ms_byte << 8) | (ls_byte & 0xFF)
        else:
            return 0
