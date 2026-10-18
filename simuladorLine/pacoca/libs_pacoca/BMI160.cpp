/*
===============================================
BMI160 accelerometer/gyroscope library for Intel(R) Curie(TM) devices.
Copyright (c) 2015 Intel Corporation.  All rights reserved.

Based on MPU6050 Arduino library provided by Jeff Rowberg as part of his
excellent I2Cdev device library: https://github.com/jrowberg/i2cdevlib

===============================================
I2Cdev device library code is placed under the MIT license
Copyright (c) 2012 Jeff Rowberg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
===============================================
*/
#include "BMI160.h"

#define ENDERECO_EEPROM_BMI160 200
#define BMI160_MARCA_CALIBRADO 0xB1   // gravado em +10 pelo calibrar()

#define BMI160_CHIP_ID 0xD1

#define BMI160_ACCEL_POWERUP_DELAY_MS 10
#define BMI160_GYRO_POWERUP_DELAY_MS 100

/* Test the sign bit and set remaining MSBs if sign bit is set */
#define BMI160_SIGN_EXTEND(val, from) \
    (((val) & (1 << ((from) - 1))) ? (int16_t)((uint16_t)(val) | (uint16_t)(0xFFFFu << (from))) : (int16_t)(val))

/******************************************************************************/


// Construtor que aceita PortaI2C
BMI160::BMI160(PortaI2C porta) {
    this->sda = porta.sda;
    this->scl = porta.scl;
    strcpy(this->descricaoPorta, porta.descricao);
    
    // Extrai número da porta da descrição (ex: "I2C-1" -> 1)
    if (porta.descricao[4] >= '1' && porta.descricao[4] <= '5') {
        this->numeroPorta = porta.descricao[4] - '0';
    } else {
        this->numeroPorta = 0;  // Porta inválida
    }
    bus = NULL;
    planoX = planoY = eixoZ = 0;
    angleZ = 0;
    restoZ = 0;
    divisorZ = BMI160_DIVISOR_Z_PADRAO;
    fifoCheia = false;
    accelOffsetX = accelOffsetY = 0;
    ultimaAtualizacao = 0;
}

// Construtor padrão
BMI160::BMI160() {
    this->sda = 0;
    this->scl = 0;
    this->numeroPorta = 0;
    strcpy(this->descricaoPorta, "I2C-0");
    bus = NULL;
    planoX = planoY = eixoZ = 0;
    angleZ = 0;
    restoZ = 0;
    divisorZ = BMI160_DIVISOR_Z_PADRAO;
    fifoCheia = false;
    accelOffsetX = accelOffsetY = 0;
    ultimaAtualizacao = 0;
}

// Método para iniciar a comunicação I2C
bool BMI160::begin() {
    bus = new SoftWire(sda, scl);
    bus->setTimeout_ms(10);
    bus->begin();
    bus->setTimeout_ms(10);
    
    // Testa a conexão
    uint8_t id = getDeviceID();
    if (id != BMI160_CHIP_ID) {
        delay(3);
        id = getDeviceID(); // Segunda tentativa
        if (id != BMI160_CHIP_ID) {
            Serial.print(F("Erro ao detectar o BMI160 na porta "));
            Serial.println(this->descricaoPorta);
            while(1);
        }
    }
    
    Serial.print(F("BMI160 detectado com sucesso na porta "));
    Serial.println(this->descricaoPorta);
    
    // Inicializa o sensor
    initialize();
    carregaCalibracao();
    return true;
}

// Implementação do serial_buffer_transfer usando SoftWire
int BMI160::serial_buffer_transfer(uint8_t *buf, unsigned tx_cnt, unsigned rx_cnt) {
    if (bus == NULL) return -1;
    
    if (rx_cnt == 0) {
        // Apenas escrita
        bus->beginTransmission(deviceAddress);
        bus->write(buf, tx_cnt);
        last_status = bus->endTransmission();
        return last_status;
    } else {
        // Escrita seguida de leitura
        bus->beginTransmission(deviceAddress);
        bus->write(buf[0]); // Envia o endereço do registrador
        last_status = bus->endTransmission();
        
        if (last_status != 0) return last_status;
        
        // Lê os dados
        bus->requestFrom(deviceAddress, (uint8_t)rx_cnt);
        for (unsigned i = 0; i < rx_cnt; i++) {
            if (bus->available()) {
                buf[i] = bus->read();
            } else {
                return -1;
            }
        }
        return 0;
    }
}

// Implementação do serial_buffer_transfer usando SoftWire
int8_t BMI160::serial_buffer_transfer_Z_Only(uint8_t *buf, uint8_t tx_cnt, uint8_t rx_cnt) {
    if (bus == NULL) return -1;
    
    if (rx_cnt == 0) {
        // Apenas escrita
        bus->beginTransmission(deviceAddress);
        bus->write(buf, tx_cnt);
        last_status = bus->endTransmission();
        return last_status;
    } else {
        // Escrita seguida de leitura
        bus->beginTransmission(deviceAddress);
        bus->write(buf[0]); // Envia o endereço do registrador
        last_status = bus->endTransmission();
        
        if (last_status != 0) return last_status;
        
        // Lê os dados
        bus->requestFrom(deviceAddress, rx_cnt);
        uint8_t totalZ = rx_cnt/3;
        // Serial.println(F("totalz:"));
        // Serial.println(totalZ);
        for (uint8_t i = 0; i < totalZ; i+=2) { 
            if (bus->available()) { //pega somente o eixo Z (últimos 2 bytes)
                bus->read();
                bus->read();
                bus->read();
                bus->read();
                buf[i] = bus->read();
                buf[i+1] = bus->read();
                // uint16_t temp = (((uint16_t)buf[i+1]) << 8) | buf[i];
                // Serial.print(F("Leu da FIFO (Z-only): "));
                // Serial.println((int16_t)temp);
            } else {
                // Serial.println(F("Iniciando mais uma leitura da FIFO (Z-only) devido a falta de dados disponíveis"));
                //bus->requestFrom(deviceAddress, rx_cnt);
                return -1;
            }
        }
        return 0;
    }
}

/******************************************************************************/

uint8_t BMI160::reg_read (uint8_t reg)
{
    uint8_t buffer[1];
    buffer[0] = reg;
    serial_buffer_transfer(buffer, 1, 1);
    return buffer[0];
}

void BMI160::reg_write(uint8_t reg, uint8_t data)
{
    uint8_t buffer[2];
    buffer[0] = reg;
    buffer[1] = data;
    serial_buffer_transfer(buffer, 2, 0);
}

void BMI160::reg_write_bits(uint8_t reg, uint8_t data, unsigned pos, unsigned len)
{
    uint8_t b = reg_read(reg);
    uint8_t mask = ((1 << len) - 1) << pos;
    data <<= pos; // shift data into correct position
    data &= mask; // zero all non-important bits in data
    b &= ~(mask); // zero all important bits in existing byte
    b |= data; // combine data with existing byte
    reg_write(reg, b);
}

uint8_t BMI160::reg_read_bits(uint8_t reg, unsigned pos, unsigned len)
{
    uint8_t b = reg_read(reg);
    uint8_t mask = (1 << len) - 1;
    b >>= pos;
    b &= mask;
    return b;
}

/******************************************************************************/

/** Power on and prepare for general usage.
 * This will activate the device and take it out of sleep mode (which must be done
 * after start-up). This function also sets both the accelerometer and the gyroscope
 * to default range settings, namely +/- 2g and +/- 250 degrees/sec.
 */
void BMI160::initialize()
{
    /* Issue a soft-reset to bring the device into a clean state */
    reg_write(BMI160_RA_CMD, BMI160_CMD_SOFT_RESET);
    delay(1);

    /* Power up the accelerometer */
    reg_write(BMI160_RA_CMD, BMI160_CMD_ACC_MODE_NORMAL);
    delay(1);
    /* Wait for power-up to complete */
    while (0x1 != reg_read_bits(BMI160_RA_PMU_STATUS,
                                BMI160_ACC_PMU_STATUS_BIT,
                                BMI160_ACC_PMU_STATUS_LEN))
        delay(1);

    /* Power up the gyroscope */
    reg_write(BMI160_RA_CMD, BMI160_CMD_GYR_MODE_NORMAL);
    delay(1);
    /* Wait for power-up to complete */
    while (0x1 != reg_read_bits(BMI160_RA_PMU_STATUS,
                                BMI160_GYR_PMU_STATUS_BIT,
                                BMI160_GYR_PMU_STATUS_LEN))
        delay(1);

    
    
    /* Set lowest data rates for gyro (25Hz) and accel (25/2Hz = 12.5Hz) */
    setGyroRate(BMI160_GYRO_RATE_25HZ);   // 25Hz - lowest rate
    setAccelRate(BMI160_ACCEL_RATE_25_2HZ);  // 12.5Hz - lowest rate
    setFullScaleGyroRange(BMI160_GYRO_RANGE_2000);
    setFullScaleAccelRange(BMI160_ACCEL_RANGE_2G);
    
    /* Enable FIFO for gyroscope only (headerless mode for simplicity) */
    setFIFOHeaderModeEnabled(false);  // Modo sem header (mais simples)
    setGyroFIFOEnabled(true);         // Habilita FIFO apenas do gyro
    resetFIFO();                      // Limpa FIFO inicial
    
    /* Only PIN1 interrupts currently supported - map all interrupts to PIN1 */
    reg_write(BMI160_RA_INT_MAP_0, 0xFF);
    reg_write(BMI160_RA_INT_MAP_1, 0xF0);
    reg_write(BMI160_RA_INT_MAP_2, 0x00);

}

/** Get Device ID.
 * This register is used to verify the identity of the device (0b11010001, 0xD1).
 * @return Device ID (should be 0xD1)
 * @see BMI160_RA_CHIP_ID
 */
uint8_t BMI160::getDeviceID() {
    return reg_read(BMI160_RA_CHIP_ID);
}

/** Verify the I2C connection.
 * Make sure the device is connected and responds as expected.
 * @return True if connection is valid, false otherwise
 */
bool BMI160::testConnection()
{
    return (BMI160_CHIP_ID == getDeviceID());
}

/** Get gyroscope output data rate.
 * The gyr_odr parameter allows setting the output data rate of the gyroscope
 * as described in the table below.
 *
 * <pre>
 *  6 =   25Hz
 *  7 =   50Hz
 *  8 =  100Hz
 *  9 =  200Hz
 * 10 =  400Hz
 * 11 =  800Hz
 * 12 = 1600Hz
 * 13 = 3200Hz
 * </pre>
 *
 * @return Current sample rate
 * @see BMI160_RA_GYRO_CONF
 * @see BMI160GyroRate
 */
uint8_t BMI160::getGyroRate() {
    return reg_read_bits(BMI160_RA_GYRO_CONF,
                         BMI160_GYRO_RATE_SEL_BIT,
                         BMI160_GYRO_RATE_SEL_LEN);
}

/** Set gyroscope output data rate.
 * @param rate New output data rate
 * @see getGyroRate()
 * @see BMI160_GYRO_RATE_25HZ
 * @see BMI160_RA_GYRO_CONF
 */
void BMI160::setGyroRate(uint8_t rate) {
    reg_write_bits(BMI160_RA_GYRO_CONF, rate,
                   BMI160_GYRO_RATE_SEL_BIT,
                   BMI160_GYRO_RATE_SEL_LEN);
}

/** Get accelerometer output data rate.
 * The acc_odr parameter allows setting the output data rate of the accelerometer
 * as described in the table below.
 *
 * <pre>
 *  5 =  25/2Hz
 *  6 =    25Hz
 *  7 =    50Hz
 *  8 =   100Hz
 *  9 =   200Hz
 * 10 =   400Hz
 * 11 =   800Hz
 * 12 =  1600Hz
 * 13 =  3200Hz
 * </pre>
 *
 * @return Current sample rate
 * @see BMI160_RA_ACCEL_CONF
 * @see BMI160AccelRate
 */
uint8_t BMI160::getAccelRate() {
    return reg_read_bits(BMI160_RA_ACCEL_CONF,
                         BMI160_ACCEL_RATE_SEL_BIT,
                         BMI160_ACCEL_RATE_SEL_LEN);
}

/** Set accelerometer output data rate.
 * @param rate New output data rate
 * @see getAccelRate()
 * @see BMI160_RA_ACCEL_CONF
 */
void BMI160::setAccelRate(uint8_t rate) {
    reg_write_bits(BMI160_RA_ACCEL_CONF, rate,
                   BMI160_ACCEL_RATE_SEL_BIT,
                   BMI160_ACCEL_RATE_SEL_LEN);
}

/** Get gyroscope digital low-pass filter mode.
 * The gyro_bwp parameter sets the gyroscope digital low pass filter configuration.
 *
 * When the filter mode is set to Normal (@see BMI160_DLPF_MODE_NORM), the filter
 * bandwidth for each respective gyroscope output data rates is shown in the table below:
 *
 * <pre>
 * ODR     | 3dB cut-off
 * --------+------------
 *    25Hz | 10.7Hz
 *    50Hz | 20.8Hz
 *   100Hz | 39.9Hz
 *   200Hz | 74.6Hz
 *   400Hz | 136.6Hz
 *   800Hz | 254.6Hz
 *  1600Hz | 523.9Hz
 *  3200Hz | 890Hz
 * </pre>
 *
 * When the filter mode is set to OSR2 (@see BMI160_DLPF_MODE_OSR2), the filter
 * bandwidths above are approximately halved.
 *
 * When the filter mode is set to OSR4 (@see BMI160_DLPF_MODE_OSR4), the filter
 * bandwidths above are approximately 4 times smaller.
 *
 * @return DLFP configuration
 * @see BMI160_RA_GYRO_CONF
 * @see BMI160DLPFMode
 */
uint8_t BMI160::getGyroDLPFMode() {
    return reg_read_bits(BMI160_RA_GYRO_CONF,
                         BMI160_GYRO_DLPF_SEL_BIT,
                         BMI160_GYRO_DLPF_SEL_LEN);
}

/** Set gyroscope digital low-pass filter configuration.
 * @param mode New DLFP configuration setting
 * @see getGyroDLPFMode()
 */
void BMI160::setGyroDLPFMode(uint8_t mode) {
    return reg_write_bits(BMI160_RA_GYRO_CONF, mode,
                          BMI160_GYRO_DLPF_SEL_BIT,
                          BMI160_GYRO_DLPF_SEL_LEN);
}

/** Get accelerometer digital low-pass filter mode.
 * The acc_bwp parameter sets the accelerometer digital low pass filter configuration.
 *
 * When the filter mode is set to Normal (@see BMI160_DLPF_MODE_NORM), the filter
 * bandwidth for each respective accelerometer output data rates is shown in the table below:
 *
 * <pre>
 * ODR     | 3dB cut-off
 * --------+--------------
 *  12.5Hz |  5.06Hz
 *    25Hz | 10.12Hz
 *    50Hz | 20.25Hz
 *   100Hz | 40.5Hz
 *   200Hz | 80Hz
 *   400Hz | 162Hz (155Hz for Z axis)
 *   800Hz | 324Hz (262Hz for Z axis)
 *  1600Hz | 684Hz (353Hz for Z axis)
 * </pre>
 *
 * When the filter mode is set to OSR2 (@see BMI160_DLPF_MODE_OSR2), the filter
 * bandwidths above are approximately halved.
 *
 * When the filter mode is set to OSR4 (@see BMI160_DLPF_MODE_OSR4), the filter
 * bandwidths above are approximately 4 times smaller.
 *
 * @return DLFP configuration
 * @see BMI160_RA_GYRO_CONF
 * @see BMI160DLPFMode
 */
uint8_t BMI160::getAccelDLPFMode() {
    return reg_read_bits(BMI160_RA_ACCEL_CONF,
                         BMI160_ACCEL_DLPF_SEL_BIT,
                         BMI160_ACCEL_DLPF_SEL_LEN);
}

/** Set accelerometer digital low-pass filter configuration.
 * @param mode New DLFP configuration setting
 * @see getAccelDLPFMode()
 */
void BMI160::setAccelDLPFMode(uint8_t mode) {
    return reg_write_bits(BMI160_RA_ACCEL_CONF, mode,
                          BMI160_ACCEL_DLPF_SEL_BIT,
                          BMI160_ACCEL_DLPF_SEL_LEN);
}

/** Get full-scale gyroscope range.
 * The gyr_range parameter allows setting the full-scale range of the gyro sensors,
 * as described in the table below.
 *
 * <pre>
 * 4 = +/-  125 degrees/sec
 * 3 = +/-  250 degrees/sec
 * 2 = +/-  500 degrees/sec
 * 1 = +/- 1000 degrees/sec
 * 0 = +/- 2000 degrees/sec
 * </pre>
 *
 * @return Current full-scale gyroscope range setting
 * @see BMI160_RA_GYRO_RANGE
 * @see BMI160GyroRange
 */
uint8_t BMI160::getFullScaleGyroRange() {
    return reg_read_bits(BMI160_RA_GYRO_RANGE,
                         BMI160_GYRO_RANGE_SEL_BIT,
                         BMI160_GYRO_RANGE_SEL_LEN);
}

/** Set full-scale gyroscope range.
 * @param range New full-scale gyroscope range value
 * @see getFullScaleGyroRange()
 */
void BMI160::setFullScaleGyroRange(uint8_t range) {
    reg_write_bits(BMI160_RA_GYRO_RANGE, range,
                   BMI160_GYRO_RANGE_SEL_BIT,
                   BMI160_GYRO_RANGE_SEL_LEN);
}

/** Get full-scale accelerometer range.
 * The FS_SEL parameter allows setting the full-scale range of the accelerometer
 * sensors, as described in the table below.
 *
 * <pre>
 *  3 = +/- 2g
 *  5 = +/- 4g
 *  8 = +/- 8g
 * 12 = +/- 16g
 * </pre>
 *
 * @return Current full-scale accelerometer range setting
 * @see BMI160_RA_ACCEL_RANGE
 * @see BMI160AccelRange
 */
uint8_t BMI160::getFullScaleAccelRange() {
    return reg_read_bits(BMI160_RA_ACCEL_RANGE,
                         BMI160_ACCEL_RANGE_SEL_BIT,
                         BMI160_ACCEL_RANGE_SEL_LEN);
}

/** Set full-scale accelerometer range.
 * @param range New full-scale accelerometer range setting
 * @see getFullScaleAccelRange()
 * @see BMI160AccelRange
 */
void BMI160::setFullScaleAccelRange(uint8_t range) {
    reg_write_bits(BMI160_RA_ACCEL_RANGE, range,
                   BMI160_ACCEL_RANGE_SEL_BIT,
                   BMI160_ACCEL_RANGE_SEL_LEN);
}

/** Get accelerometer offset compensation enabled value.
 * @see getXAccelOffset()
 * @see BMI160_RA_OFFSET_6
 */
bool BMI160::getAccelOffsetEnabled() {
    return !!(reg_read_bits(BMI160_RA_OFFSET_6,
                            BMI160_ACC_OFFSET_EN,
                            1));
}

/** Set accelerometer offset compensation enabled value.
 * @see getXAccelOffset()
 * @see BMI160_RA_OFFSET_6
 */
void BMI160::setAccelOffsetEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_OFFSET_6, enabled ? 0x1 : 0,
                   BMI160_ACC_OFFSET_EN,
                   1);
}

/** Execute internal calibration to generate Accelerometer X-Axis offset value.
 * This populates the Accelerometer offset compensation value for the X-Axis only.
 * These can be retrieved using the getXAccelOffset() methods.
 * Note that this procedure may take up to 250ms to complete.
 *
 * IMPORTANT: The user MUST ensure NO movement and correct orientation of the
 * BMI160 device occurs while this auto-calibration process is active.
 * For example, to calibrate to a target of 0g on the X-axis, the BMI160 device
 * must be resting horizontally as shown in Section 5.2 of the BMI160 Data Sheet.
 *
 * To enable offset compensation, @see setAccelOffsetEnabled()
 *
 * @param target X-axis target value (0 = 0g, 1 = +1g, -1 = -1g)
 * @see setAccelOffsetEnabled()
 * @see getXAccelOffset()
 * @see BMI160_RA_FOC_CONF
 * @see BMI160_RA_CMD
 */
void BMI160::autoCalibrateXAccelOffset(int target) {
    uint8_t foc_conf;
    if (target == 1)
        foc_conf = (0x1 << BMI160_FOC_ACC_X_BIT);
    else if (target == -1)
        foc_conf = (0x2 << BMI160_FOC_ACC_X_BIT);
    else if (target == 0)
        foc_conf = (0x3 << BMI160_FOC_ACC_X_BIT);
    else
        return;  /* Invalid target value */

    reg_write(BMI160_RA_FOC_CONF, foc_conf);
    reg_write(BMI160_RA_CMD, BMI160_CMD_START_FOC);
    uint32_t t0 = millis();
    while (!(reg_read_bits(BMI160_RA_STATUS,
                           BMI160_STATUS_FOC_RDY,
                           1)) && (millis() - t0) < 1000)
        delay(1);
}

/** Execute internal calibration to generate Accelerometer Y-Axis offset value.
 * This populates the Accelerometer offset compensation value for the Y-Axis only.
 * These can be retrieved using the getYAccelOffset() methods.
 * Note that this procedure may take up to 250ms to complete.
 *
 * IMPORTANT: The user MUST ensure NO movement and correct orientation of the
 * BMI160 device occurs while this auto-calibration process is active.
 * For example, to calibrate to a target of 0g on the Y-axis, the BMI160 device
 * must be resting horizontally as shown in Section 5.2 of the BMI160 Data Sheet.
 *
 * To enable offset compensation, @see setAccelOffsetEnabled()
 *
 * @param target Y-axis target value (0 = 0g, 1 = +1g, -1 = -1g)
 * @see setAccelOffsetEnabled()
 * @see getYAccelOffset()
 * @see BMI160_RA_FOC_CONF
 * @see BMI160_RA_CMD
 */
void BMI160::autoCalibrateYAccelOffset(int target) {
    uint8_t foc_conf;
    if (target == 1)
        foc_conf = (0x1 << BMI160_FOC_ACC_Y_BIT);
    else if (target == -1)
        foc_conf = (0x2 << BMI160_FOC_ACC_Y_BIT);
    else if (target == 0)
        foc_conf = (0x3 << BMI160_FOC_ACC_Y_BIT);
    else
        return;  /* Invalid target value */

    reg_write(BMI160_RA_FOC_CONF, foc_conf);
    reg_write(BMI160_RA_CMD, BMI160_CMD_START_FOC);
    uint32_t t0 = millis();
    while (!(reg_read_bits(BMI160_RA_STATUS,
                           BMI160_STATUS_FOC_RDY,
                           1)) && (millis() - t0) < 1000)
        delay(1);
}

/** Execute internal calibration to generate Accelerometer Z-Axis offset value.
 * This populates the Accelerometer offset compensation value for the Z-Axis only.
 * These can be retrieved using the getZAccelOffset() methods.
 * Note that this procedure may take up to 250ms to complete.
 *
 * IMPORTANT: The user MUST ensure NO movement and correct orientation of the
 * BMI160 device occurs while this auto-calibration process is active.
 * For example, to calibrate to a target of +1g on the Z-axis, the BMI160 device
 * must be resting horizontally as shown in Section 5.2 of the BMI160 Data Sheet.
 *
 * To enable offset compensation, @see setAccelOffsetEnabled()
 *
 * @param target Z-axis target value (0 = 0g, 1 = +1g, -1 = -1g)
 * @see setAccelOffsetEnabled()
 * @see getZAccelOffset()
 * @see BMI160_RA_FOC_CONF
 * @see BMI160_RA_CMD
 */
void BMI160::autoCalibrateZAccelOffset(int target) {
    uint8_t foc_conf;
    if (target == 1)
        foc_conf = (0x1 << BMI160_FOC_ACC_Z_BIT);
    else if (target == -1)
        foc_conf = (0x2 << BMI160_FOC_ACC_Z_BIT);
    else if (target == 0)
        foc_conf = (0x3 << BMI160_FOC_ACC_Z_BIT);
    else
        return;  /* Invalid target value */

    reg_write(BMI160_RA_FOC_CONF, foc_conf);
    reg_write(BMI160_RA_CMD, BMI160_CMD_START_FOC);
    uint32_t t0 = millis();
    while (!(reg_read_bits(BMI160_RA_STATUS,
                           BMI160_STATUS_FOC_RDY,
                           1)) && (millis() - t0) < 1000)
        delay(1);
}

/** Get offset compensation value for accelerometer X-axis data.
 * The value is represented as an 8-bit two-complement number in
 * units of 3.9mg per LSB.
 * @see BMI160_RA_OFFSET_0
 */
int8_t BMI160::getXAccelOffset() {
    return reg_read(BMI160_RA_OFFSET_0);
}

/** Set offset compensation value for accelerometer X-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateXAccelOffset().
 * @see getXAccelOffset()
 * @see BMI160_RA_OFFSET_0
 */
void BMI160::setXAccelOffset(int8_t offset) {
    reg_write(BMI160_RA_OFFSET_0, offset);
    getAccelerationX(); /* Read and discard the next data value */
}

/** Get offset compensation value for accelerometer Y-axis data.
 * The value is represented as an 8-bit two-complement number in
 * units of 3.9mg per LSB.
 * @see BMI160_RA_OFFSET_1
 */
int8_t BMI160::getYAccelOffset() {
    return reg_read(BMI160_RA_OFFSET_1);
}

/** Set offset compensation value for accelerometer Y-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateYAccelOffset().
 * @see getYAccelOffset()
 * @see BMI160_RA_OFFSET_1
 */
void BMI160::setYAccelOffset(int8_t offset) {
    reg_write(BMI160_RA_OFFSET_1, offset);
    getAccelerationY(); /* Read and discard the next data value */
}

/** Get offset compensation value for accelerometer Z-axis data.
 * The value is represented as an 8-bit two-complement number in
 * units of 3.9mg per LSB.
 * @see BMI160_RA_OFFSET_2
 */
int8_t BMI160::getZAccelOffset() {
    return reg_read(BMI160_RA_OFFSET_2);
}

/** Set offset compensation value for accelerometer Z-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateZAccelOffset().
 * @see getZAccelOffset()
 * @see BMI160_RA_OFFSET_2
 */
void BMI160::setZAccelOffset(int8_t offset) {
    reg_write(BMI160_RA_OFFSET_2, offset);
    getAccelerationZ(); /* Read and discard the next data value */
}

/** Get gyroscope offset compensation enabled value.
 * @see getXGyroOffset()
 * @see BMI160_RA_OFFSET_6
 */
bool BMI160::getGyroOffsetEnabled() {
    return !!(reg_read_bits(BMI160_RA_OFFSET_6,
                            BMI160_GYR_OFFSET_EN,
                            1));
}

/** Set gyroscope offset compensation enabled value.
 * @see getXGyroOffset()
 * @see BMI160_RA_OFFSET_6
 */
void BMI160::setGyroOffsetEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_OFFSET_6, enabled ? 0x1 : 0,
                   BMI160_GYR_OFFSET_EN,
                   1) ;
}

/** Execute internal calibration to generate Gyro offset values.
 * This populates the Gyro offset compensation values for all 3 axes.
 * These can be retrieved using the get[X/Y/Z]GyroOffset() methods.
 * Note that this procedure may take up to 250ms to complete.
 *
 * IMPORTANT: The user MUST ensure that NO rotation of the BMI160 device
 * occurs while this auto-calibration process is active.
 *
 * To enable offset compensation, @see setGyroOffsetEnabled()
 * @see setGyroOffsetEnabled()
 * @see getXGyroOffset()
 * @see getYGyroOffset()
 * @see getZGyroOffset()
 * @see BMI160_RA_FOC_CONF
 * @see BMI160_RA_CMD
 */
void BMI160::autoCalibrateGyroOffset() {
    uint8_t foc_conf = (1 << BMI160_FOC_GYR_EN);
    reg_write(BMI160_RA_FOC_CONF, foc_conf);
    reg_write(BMI160_RA_CMD, BMI160_CMD_START_FOC);
    uint32_t t0 = millis();
    while (!(reg_read_bits(BMI160_RA_STATUS,
                           BMI160_STATUS_FOC_RDY,
                           1)) && (millis() - t0) < 1000)
        delay(1);
}

/** Get offset compensation value for gyroscope X-axis data.
 * The value is represented as an 10-bit two-complement number in
 * units of 0.061 degrees/s per LSB (sign-extended for int16_t type).
 * @see BMI160_RA_OFFSET_3
 * @see BMI160_RA_OFFSET_6
 */
int16_t BMI160::getXGyroOffset() {
    int16_t offset = reg_read(BMI160_RA_OFFSET_3);
    offset |= (int16_t)(reg_read_bits(BMI160_RA_OFFSET_6,
                                      BMI160_GYR_OFFSET_X_MSB_BIT,
                                      BMI160_GYR_OFFSET_X_MSB_LEN)) << 8;
    return BMI160_SIGN_EXTEND(offset, 10);
}

/** Set offset compensation value for gyroscope X-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateGyroOffset().
 * @see getXGyroOffset()
 * @see BMI160_RA_OFFSET_3
 * @see BMI160_RA_OFFSET_6
 */
void BMI160::setXGyroOffset(int16_t offset) {
    reg_write(BMI160_RA_OFFSET_3, offset);
    reg_write_bits(BMI160_RA_OFFSET_6, offset >> 8,
                   BMI160_GYR_OFFSET_X_MSB_BIT,
                   BMI160_GYR_OFFSET_X_MSB_LEN);
    getRotationX(); /* Read and discard the next data value */
}

/** Get offset compensation value for gyroscope Y-axis data.
 * The value is represented as an 10-bit two-complement number in
 * units of 0.061 degrees/s per LSB (sign-extended for int16_t type).
 * @see BMI160_RA_OFFSET_4
 * @see BMI160_RA_OFFSET_6
 */
int16_t BMI160::getYGyroOffset() {
    int16_t offset = reg_read(BMI160_RA_OFFSET_4);
    offset |= (int16_t)(reg_read_bits(BMI160_RA_OFFSET_6,
                                      BMI160_GYR_OFFSET_Y_MSB_BIT,
                                      BMI160_GYR_OFFSET_Y_MSB_LEN)) << 8;
    return BMI160_SIGN_EXTEND(offset, 10);
}

/** Set offset compensation value for gyroscope Y-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateGyroOffset().
 * @see getYGyroOffset()
 * @see BMI160_RA_OFFSET_4
 * @see BMI160_RA_OFFSET_6
 */
void BMI160::setYGyroOffset(int16_t offset) {
    reg_write(BMI160_RA_OFFSET_4, offset);
    reg_write_bits(BMI160_RA_OFFSET_6, offset >> 8,
                   BMI160_GYR_OFFSET_Y_MSB_BIT,
                   BMI160_GYR_OFFSET_Y_MSB_LEN);
    getRotationY(); /* Read and discard the next data value */
}

/** Get offset compensation value for gyroscope Z-axis data.
 * The value is represented as an 10-bit two-complement number in
 * units of 0.061 degrees/s per LSB (sign-extended for int16_t type).
 * @see BMI160_RA_OFFSET_5
 * @see BMI160_RA_OFFSET_6
 */
int16_t BMI160::getZGyroOffset() {
    int16_t offset = reg_read(BMI160_RA_OFFSET_5);
    offset |= (int16_t)(reg_read_bits(BMI160_RA_OFFSET_6,
                                      BMI160_GYR_OFFSET_Z_MSB_BIT,
                                      BMI160_GYR_OFFSET_Z_MSB_LEN)) << 8;
    return BMI160_SIGN_EXTEND(offset, 10);
}

/** Set offset compensation value for gyroscope Z-axis data.
 * This is used for applying manual calibration constants if required.
 * For auto-calibration, @see autoCalibrateGyroOffset().
 * @see getZGyroOffset()
 * @see BMI160_RA_OFFSET_5
 * @see BMI160_RA_OFFSET_6
 */
void BMI160::setZGyroOffset(int16_t offset) {
    reg_write(BMI160_RA_OFFSET_5, offset);
    reg_write_bits(BMI160_RA_OFFSET_6, offset >> 8,
                   BMI160_GYR_OFFSET_Z_MSB_BIT,
                   BMI160_GYR_OFFSET_Z_MSB_LEN);
    getRotationZ(); /* Read and discard the next data value */
}

/** Get accelerometer FIFO enabled value.
 * When set to 1, this bit enables accelerometer data samples to be
 * written into the FIFO buffer.
 * @return Current accelerometer FIFO enabled value
 * @see BMI160_RA_FIFO_CONFIG_1
 */
bool BMI160::getAccelFIFOEnabled() {
    return !!(reg_read_bits(BMI160_RA_FIFO_CONFIG_1,
                            BMI160_FIFO_ACC_EN_BIT,
                            1));
}

/** Set accelerometer FIFO enabled value.
 * @param enabled New accelerometer FIFO enabled value
 * @see getAccelFIFOEnabled()
 * @see BMI160_RA_FIFO_CONFIG_1
 */
void BMI160::setAccelFIFOEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_FIFO_CONFIG_1, enabled ? 0x1 : 0,
                   BMI160_FIFO_ACC_EN_BIT,
                   1);
}

/** Get gyroscope FIFO enabled value.
 * When set to 1, this bit enables gyroscope data samples to be
 * written into the FIFO buffer.
 * @return Current gyroscope FIFO enabled value
 * @see BMI160_RA_FIFO_CONFIG_1
 */
bool BMI160::getGyroFIFOEnabled() {
    return !!(reg_read_bits(BMI160_RA_FIFO_CONFIG_1,
                            BMI160_FIFO_GYR_EN_BIT,
                            1));
}

/** Set gyroscope FIFO enabled value.
 * @param enabled New gyroscope FIFO enabled value
 * @see getGyroFIFOEnabled()
 * @see BMI160_RA_FIFO_CONFIG_1
 */
void BMI160::setGyroFIFOEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_FIFO_CONFIG_1, enabled ? 0x1 : 0,
                   BMI160_FIFO_GYR_EN_BIT,
                   1);
}

/** Get current FIFO buffer size.
 * This value indicates the number of bytes stored in the FIFO buffer. This
 * number is in turn the number of bytes that can be read from the FIFO buffer.
 *
 * In "headerless" FIFO mode, it is directly proportional to the number of
 * samples available given the set of sensor data bound to be stored in the
 * FIFO. See @ref getFIFOHeaderModeEnabled().
 *
 * @return Current FIFO buffer size
 * @see BMI160_RA_FIFO_LENGTH_0
 */
uint16_t BMI160::getFIFOCount() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_FIFO_LENGTH_0;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Reset the FIFO.
 * This command clears all data in the FIFO buffer.  It is recommended
 * to invoke this after reconfiguring the FIFO.
 * 
 * @see BMI160_RA_CMD
 * @see BMI160_CMD_FIFO_FLUSH
 */
void BMI160::resetFIFO() {
    reg_write(BMI160_RA_CMD, BMI160_CMD_FIFO_FLUSH);
}

/** Reset the Interrupt controller.
 * This command clears interrupt status registers and latched interrupts.
 * 
 * @see BMI160_RA_CMD
 * @see BMI160_CMD_FIFO_FLUSH
 */
void BMI160::resetInterrupt() {
    reg_write(BMI160_RA_CMD, BMI160_CMD_INT_RESET);
}

/** Get FIFO Header-Mode enabled status.
 * When this bit is set to 0, the FIFO header-mode is disabled, and frames
 * read from the FIFO will be headerless (raw sensor data only).
 * When this bit is set to 1, the FIFO header-mode is enabled, and frames
 * read from the FIFO will include headers.
 *
 * For more information on the FIFO modes and data formats, please refer
 * to Section 2.5 of the BMI160 Data Sheet.
 *
 * @return Current FIFO Header-Mode enabled status
 * @see BMI160_RA_FIFO_CONFIG_1
 * @see BMI160_FIFO_HEADER_EN_BIT
 */
bool BMI160::getFIFOHeaderModeEnabled() {
    return !!(reg_read_bits(BMI160_RA_FIFO_CONFIG_1,
                            BMI160_FIFO_HEADER_EN_BIT,
                            1));
}

/** Set FIFO Header-Mode enabled status.
 * @param enabled New FIFO Header-Mode enabled status
 * @see getFIFOHeaderModeEnabled()
 * @see BMI160_RA_FIFO_CONFIG_1
 * @see BMI160_FIFO_HEADER_EN_BIT
 */
void BMI160::setFIFOHeaderModeEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_FIFO_CONFIG_1, enabled ? 0x1 : 0,
                   BMI160_FIFO_HEADER_EN_BIT,
                   1);
}

/** Get data frames from FIFO buffer.
 * This register is used to read and write data frames from the FIFO buffer.
 * Data is written to the FIFO in order of DATA register number (from lowest
 * to highest) corresponding to the FIFO data sources enabled (@see
 * getGyroFIFOEnabled() and getAccelFIFOEnabled()).
 *
 * The data frame format depends on the enabled data sources and also on
 * the FIFO header-mode setting (@see getFIFOHeaderModeEnabled()).
 *
 * It is strongly recommended, where possible, to read whole frames from the
 * FIFO.  Partially-read frames will be repeated until fully read out.
 *
 * If the FIFO buffer has filled to the point where subsequent writes may
 * cause data loss, the status bit ffull_int is automatically set to 1. This bit
 * is located in INT_STATUS[1]. When the FIFO buffer has overflowed, the oldest
 * data will be lost and new data will be written to the FIFO.
 *
 * If the FIFO buffer is empty, reading this register will return a magic number
 * (@see BMI160_FIFO_DATA_INVALID) until new data is available. The user should
 * check FIFO_LENGTH to ensure that the FIFO buffer is not read when empty (see
 * @getFIFOCount()).
 *
 * @return Data frames from FIFO buffer
 */
void BMI160::getFIFOBytes(uint8_t *data, uint16_t length) {
    if (length) {
        data[0] = BMI160_RA_FIFO_DATA;
        serial_buffer_transfer(data, 1, length);
    }
}

//maximo de 255 bytes
void BMI160::getFIFOBytesZOnly(uint8_t *data, uint8_t length) {
    if (length) {
        data[0] = BMI160_RA_FIFO_DATA;
        serial_buffer_transfer_Z_Only(data, 1, length);
    }
}


/** Get full set of interrupt status bits from INT_STATUS[0] register.
 * Interrupts are typically cleared automatically.
 * Please refer to the BMI160 Data Sheet for more information.
 * @return Current interrupt status
 * @see BMI160_RA_INT_STATUS_0
 */
uint8_t BMI160::getIntStatus0() {
    return reg_read(BMI160_RA_INT_STATUS_0);
}

/** Get full set of interrupt status bits from INT_STATUS[1] register.
 * Interrupts are typically cleared automatically.
 * Please refer to the BMI160 Data Sheet for more information.
 * @return Current interrupt status
 * @see BMI160_RA_INT_STATUS_1
 */
uint8_t BMI160::getIntStatus1() {
    return reg_read(BMI160_RA_INT_STATUS_1);
}

/** Get full set of interrupt status bits from INT_STATUS[2] register.
 * Interrupts are typically cleared automatically.
 * Please refer to the BMI160 Data Sheet for more information.
 * @return Current interrupt status
 * @see BMI160_RA_INT_STATUS_2
 */
uint8_t BMI160::getIntStatus2() {
    return reg_read(BMI160_RA_INT_STATUS_2);
}

/** Get full set of interrupt status bits from INT_STATUS[3] register.
 * Interrupts are typically cleared automatically.
 * Please refer to the BMI160 Data Sheet for more information.
 * @return Current interrupt status
 * @see BMI160_RA_INT_STATUS_3
 */
uint8_t BMI160::getIntStatus3() {
    return reg_read(BMI160_RA_INT_STATUS_3);
}

/** Get interrupt logic level mode.
 * Will be set 0 for active-high, 1 for active-low.
 * @return Current interrupt mode (0=active-high, 1=active-low)
 * @see BMI160_RA_INT_OUT_CTRL
 * @see BMI160_INT1_LVL
 */
bool BMI160::getInterruptMode() {
    return !(reg_read_bits(BMI160_RA_INT_OUT_CTRL,
                           BMI160_INT1_LVL,
                           1));
}

/** Set interrupt logic level mode.
 * @param mode New interrupt mode (0=active-high, 1=active-low)
 * @see getInterruptMode()
 * @see BMI160_RA_INT_OUT_CTRL
 * @see BMI160_INT1_LVL
 */
void BMI160::setInterruptMode(bool mode) {
    reg_write_bits(BMI160_RA_INT_OUT_CTRL, mode ? 0x0 : 0x1,
                   BMI160_INT1_LVL,
                   1);
}

/** Get interrupt drive mode.
 * Will be set 0 for push-pull, 1 for open-drain.
 * @return Current interrupt drive mode (0=push-pull, 1=open-drain)
 * @see BMI160_RA_INT_OUT_CTRL
 * @see BMI160_INT1_OD
 */
bool BMI160::getInterruptDrive() {
    return !!(reg_read_bits(BMI160_RA_INT_OUT_CTRL,
                            BMI160_INT1_OD,
                            1));
}

/** Set interrupt drive mode.
 * @param drive New interrupt drive mode (0=push-pull, 1=open-drain)
 * @see getInterruptDrive()
 * @see MPU6050_RA_INT_PIN_CFG
 * @see MPU6050_INTCFG_INT_OPEN_BIT
 */
void BMI160::setInterruptDrive(bool drive) {
    reg_write_bits(BMI160_RA_INT_OUT_CTRL, drive ? 0x1 : 0x0,
                   BMI160_INT1_OD,
                   1);
}

/** Get interrupt latch mode.  The following options are available:
 *
 * <pre>
 * Latch Mode    | Interrupt Latching
 * --------------+-------------------------
 * 0             | non-latched
 * 1             | temporary, 312.5us pulse
 * 2             | temporary,   625us pulse
 * 3             | temporary,  1.25ms pulse
 * 4             | temporary,   2.5ms pulse
 * 5             | temporary,     5ms pulse
 * 6             | temporary,    10ms pulse
 * 7             | temporary,    20ms pulse
 * 8             | temporary,    40ms pulse
 * 9             | temporary,    80ms pulse
 * 10            | temporary,   160ms pulse
 * 11            | temporary,   320ms pulse
 * 12            | temporary,   640ms pulse
 * 13            | temporary,  1.28s pulse
 * 14            | temporary,  2.56s pulse
 * 15            | latched until cleared (@see resetInterrupt())
 * </pre>
 *
 * Note that latching does not apply to the following interrupt sources:
 * - Data Ready
 * - Orientation (including Flat) detection
 *
 * @return Current latch mode
 * @see BMI160_RA_INT_LATCH
 * @see BMI160InterruptLatchMode
 */
uint8_t BMI160::getInterruptLatch() {
    return reg_read_bits(BMI160_RA_INT_LATCH,
                         BMI160_LATCH_MODE_BIT,
                         BMI160_LATCH_MODE_LEN);
}

/** Set interrupt latch mode.
 * @param latch New latch mode
 * @see getInterruptLatch()
 * @see BMI160_RA_INT_LATCH
 * @see BMI160InterruptLatchMode
 */
void BMI160::setInterruptLatch(uint8_t mode) {
    reg_write_bits(BMI160_RA_INT_LATCH, mode,
                   BMI160_LATCH_MODE_BIT,
                   BMI160_LATCH_MODE_LEN);
}

/** Get interrupt enabled status.
 * @return Current interrupt enabled status
 * @see BMI160_RA_INT_OUT_CTRL
 * @see BMI160_INT1_OUTPUT_EN
 **/
bool BMI160::getIntEnabled() {
    return !!(reg_read_bits(BMI160_RA_INT_OUT_CTRL,
                            BMI160_INT1_OUTPUT_EN,
                            1));
}

/** Set interrupt enabled status.
 * @param enabled New interrupt enabled status
 * @see BMI160_RA_INT_OUT_CTRL
 * @see BMI160_INT1_OUTPUT_EN
 **/
void BMI160::setIntEnabled(bool enabled) {
    reg_write_bits(BMI160_RA_INT_OUT_CTRL, enabled ? 0x1 : 0,
                   BMI160_INT1_OUTPUT_EN,
                   1);
}

/** Get raw 6-axis motion sensor readings (accel/gyro).
 * Retrieves all currently available motion sensor values.
 * @param ax 16-bit signed integer container for accelerometer X-axis value
 * @param ay 16-bit signed integer container for accelerometer Y-axis value
 * @param az 16-bit signed integer container for accelerometer Z-axis value
 * @param gx 16-bit signed integer container for gyroscope X-axis value
 * @param gy 16-bit signed integer container for gyroscope Y-axis value
 * @param gz 16-bit signed integer container for gyroscope Z-axis value
 * @see getAcceleration()
 * @see getRotation()
 * @see BMI160_RA_GYRO_X_L
 */
void BMI160::getMotion6(int16_t* ax, int16_t* ay, int16_t* az, int16_t* gx, int16_t* gy, int16_t* gz) {
    uint8_t buffer[12];
    buffer[0] = BMI160_RA_GYRO_X_L;
    serial_buffer_transfer(buffer, 1, 12);
    *gx = (((int16_t)buffer[1])  << 8) | buffer[0];
    *gy = (((int16_t)buffer[3])  << 8) | buffer[2];
    *gz = (((int16_t)buffer[5])  << 8) | buffer[4];
    *ax = (((int16_t)buffer[7])  << 8) | buffer[6];
    *ay = (((int16_t)buffer[9])  << 8) | buffer[8];
    *az = (((int16_t)buffer[11]) << 8) | buffer[10];
}

/** Get 3-axis accelerometer readings.
 * These registers store the most recent accelerometer measurements.
 * Accelerometer measurements are written to these registers at the Output Data Rate
 * as configured by @see getAccelRate()
 *
 * The accelerometer measurement registers, along with the temperature
 * measurement registers, gyroscope measurement registers, and external sensor
 * data registers, are composed of two sets of registers: an internal register
 * set and a user-facing read register set.
 *
 * The data within the accelerometer sensors' internal register set is always
 * updated at the Output Data Rate. Meanwhile, the user-facing read register set
 * duplicates the internal register set's data values whenever the serial
 * interface is idle. This guarantees that a burst read of sensor registers will
 * read measurements from the same sampling instant. Note that if burst reads
 * are not used, the user is responsible for ensuring a set of single byte reads
 * correspond to a single sampling instant by checking the Data Ready interrupt.
 *
 * Each 16-bit accelerometer measurement has a full scale configured by
 * @setFullScaleAccelRange. For each full scale setting, the accelerometers'
 * sensitivity per LSB is shown in the table below:
 *
 * <pre>
 * Full Scale Range | LSB Sensitivity
 * -----------------+----------------
 * +/- 2g           | 8192 LSB/mg
 * +/- 4g           | 4096 LSB/mg
 * +/- 8g           | 2048 LSB/mg
 * +/- 16g          | 1024 LSB/mg
 * </pre>
 *
 * @param x 16-bit signed integer container for X-axis acceleration
 * @param y 16-bit signed integer container for Y-axis acceleration
 * @param z 16-bit signed integer container for Z-axis acceleration
 * @see BMI160_RA_ACCEL_X_L
 */
void BMI160::getAcceleration(int16_t* x, int16_t* y, int16_t* z) {
    uint8_t buffer[6];
    buffer[0] = BMI160_RA_ACCEL_X_L;
    serial_buffer_transfer(buffer, 1, 6);
    *x = (((int16_t)buffer[1]) << 8) | buffer[0];
    *y = (((int16_t)buffer[3]) << 8) | buffer[2];
    *z = (((int16_t)buffer[5]) << 8) | buffer[4];
}

/** Get X-axis accelerometer reading.
 * @return X-axis acceleration measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_ACCEL_X_L
 */
int16_t BMI160::getAccelerationX() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_ACCEL_X_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get Y-axis accelerometer reading.
 * @return Y-axis acceleration measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_ACCEL_Y_L
 */
int16_t BMI160::getAccelerationY() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_ACCEL_Y_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get Z-axis accelerometer reading.
 * @return Z-axis acceleration measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_ACCEL_Z_L
 */
int16_t BMI160::getAccelerationZ() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_ACCEL_Z_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get current internal temperature as a signed 16-bit integer.
 *  The resolution is typically 1/2^9 degrees Celcius per LSB, at an
 *  offset of 23 degrees Celcius.  For example:
 *
 * <pre>
 * Value    | Temperature
 * ---------+----------------
 * 0x7FFF   | 87 - 1/2^9 degrees C
 * ...      | ...
 * 0x0000   | 23 degrees C
 * ...      | ...
 * 0x8001   | -41 + 1/2^9 degrees C
 * 0x8000   | Invalid
 *
 * @return Temperature reading in 16-bit 2's complement format
 * @see BMI160_RA_TEMP_L
 */
int16_t BMI160::getTemperature() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_TEMP_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get 3-axis gyroscope readings.
 * These gyroscope measurement registers, along with the accelerometer
 * measurement registers, temperature measurement registers, and external sensor
 * data registers, are composed of two sets of registers: an internal register
 * set and a user-facing read register set.
 * The data within the gyroscope sensors' internal register set is always
 * updated at the Output Data Rate. Meanwhile, the user-facing read register set
 * duplicates the internal register set's data values whenever the serial
 * interface is idle. This guarantees that a burst read of sensor registers will
 * read measurements from the same sampling instant. Note that if burst reads
 * are not used, the user is responsible for ensuring a set of single byte reads
 * correspond to a single sampling instant by checking the Data Ready interrupt.
 *
 * Each 16-bit gyroscope measurement has a full scale configured by
 * @setFullScaleGyroRange(). For each full scale setting, the gyroscopes'
 * sensitivity per LSB is shown in the table below:
 *
 * <pre>
 * Full Scale Range   | LSB Sensitivity
 * -------------------+----------------
 * +/- 125  degrees/s | 262.4 LSB/deg/s
 * +/- 250  degrees/s | 131.2 LSB/deg/s
 * +/- 500  degrees/s | 65.5  LSB/deg/s
 * +/- 1000 degrees/s | 32.8  LSB/deg/s
 * +/- 2000 degrees/s | 16.4  LSB/deg/s
 * </pre>
 *
 * @param x 16-bit signed integer container for X-axis rotation
 * @param y 16-bit signed integer container for Y-axis rotation
 * @param z 16-bit signed integer container for Z-axis rotation
 * @see getMotion6()
 * @see BMI160_RA_GYRO_X_L
 */
void BMI160::getRotation(int16_t* x, int16_t* y, int16_t* z) {
    uint8_t buffer[6];
    buffer[0] = BMI160_RA_GYRO_X_L;
    serial_buffer_transfer(buffer, 1, 6);
    *x = (((int16_t)buffer[1]) << 8) | buffer[0];
    *y = (((int16_t)buffer[3]) << 8) | buffer[2];
    *z = (((int16_t)buffer[5]) << 8) | buffer[4];
}

/** Get X-axis gyroscope reading.
 * @return X-axis rotation measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_GYRO_X_L
 */
int16_t BMI160::getRotationX() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_GYRO_X_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get Y-axis gyroscope reading.
 * @return Y-axis rotation measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_GYRO_Y_L
 */
int16_t BMI160::getRotationY() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_GYRO_Y_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Get Z-axis gyroscope reading.
 * @return Z-axis rotation measurement in 16-bit 2's complement format
 * @see getMotion6()
 * @see BMI160_RA_GYRO_Z_L
 */
int16_t BMI160::getRotationZ() {
    uint8_t buffer[2];
    buffer[0] = BMI160_RA_GYRO_Z_L;
    serial_buffer_transfer(buffer, 1, 2);
    return (((int16_t)buffer[1]) << 8) | buffer[0];
}

/** Read a BMI160 register directly.
 * @param reg register address
 * @return 8-bit register value
 */
uint8_t BMI160::getRegister(uint8_t reg) {
    return reg_read(reg);
}

/** Write a BMI160 register directly.
 * @param reg register address
 * @param data 8-bit register value
 */
void BMI160::setRegister(uint8_t reg, uint8_t data) {
    reg_write(reg, data);
}

void BMI160::atualizaDados(){
    if(millis() - ultimaAtualizacao < 40) // Atualiza a cada 40ms
        return;
    ultimaAtualizacao = millis();
    
    // Le acelerometro direto para calcular inclinacao instantanea
    int16_t ax, ay, az;
    getAcceleration(&ax, &ay, &az);
    
    // Aproximacao simples de inclinacao usando apenas acelerometro
    // Aproximacao linear simples (funciona bem para angulos pequenos)
    this->planoX = ((int32_t)(ay - accelOffsetY) * 90) >> 15;  // ~+/-90 graus
    this->planoY = ((int32_t)(ax - accelOffsetX) * 90) >> 15;  // ~+/-90 graus

    lerFIFO();
}

// Integra TODAS as amostras do giro que estao na FIFO do BMI160.
// - Nao usa resetFIFO(): a amostra que chega durante a leitura fica na FIFO
//   para a proxima vez (antes ela era apagada e o giro "sumia").
// - Le em pedacos de ate 30 bytes (o buffer do SoftWire tem 32), entao
//   da conta da FIFO inteira: 1024 bytes = 170 amostras = 6,8 s a 25 Hz.
//   Pode usar delay() longo no meio de uma curva sem perder giro.
// - Guarda o resto da divisao, para nao perder fracao de grau a cada leitura.
void BMI160::lerFIFO(){
    uint8_t b[2];
    b[0] = BMI160_RA_FIFO_LENGTH_0;
    if (serial_buffer_transfer(b, 1, 2) != 0) return;
    uint16_t bytes = ((uint16_t)(b[1] & 0x07) << 8) | b[0];
    if (bytes >= 1020) fifoCheia = true;          // FIFO cheia: amostras antigas foram perdidas
    bytes -= bytes % 6;                           // so quadros inteiros (gx, gy, gz)

    int32_t soma = 0;
    while (bytes > 0) {
        uint8_t n = (bytes > 30) ? 30 : (uint8_t)bytes;   // 5 quadros (buffer do SoftWire: 32)
        bus->beginTransmission(deviceAddress);
        bus->write(BMI160_RA_FIFO_DATA);
        last_status = bus->endTransmission();
        if (last_status != 0) break;
        uint8_t lidos = bus->requestFrom(deviceAddress, n);
        uint8_t i = 0;
        for (; (uint8_t)(i + 6) <= lidos; i += 6) {
            bus->read(); bus->read();              // gx
            bus->read(); bus->read();              // gy
            uint8_t lo = bus->read();
            uint8_t hi = bus->read();
            soma += (int16_t)(((uint16_t)hi << 8) | lo);
        }
        if (lidos != n) break;                    // erro de I2C: o resto fica para a proxima
        bytes -= n;
    }

    // centesimos de grau = soma * 100 / divisorZ
    // divisorZ = 16,4 LSB/(grau/s) * 25 amostras/s = 410 (faixa de 2000 graus/s, 25 Hz)
    restoZ += soma * 100;
    angleZ += restoZ / divisorZ;
    restoZ %= divisorZ;

    // eixoZ em decimos de grau (getEixoZ()/10 = graus)
    this->eixoZ = (int16_t)(angleZ / 10);
}

void BMI160::setDivisorZ(int16_t divisor){
    if (divisor > 0) divisorZ = divisor;
}

bool BMI160::fifoEstourou(){
    bool f = fifoCheia;
    fifoCheia = false;
    return f;
}

int16_t BMI160::getPlanoX(){
    if(millis() - ultimaAtualizacao > 40) // se passaram mais de 40ms desde a ultima leitura, atualiza os dados
        this->atualizaDados();
    return this->planoX;
}

int16_t BMI160::getPlanoY(){
    if(millis() - ultimaAtualizacao > 40) // se passaram mais de 40ms desde a ultima leitura, atualiza os dados
        this->atualizaDados();
    return this->planoY;
}

int16_t BMI160::getEixoZ(){
    if(millis() - ultimaAtualizacao > 40) // se passaram mais de 40ms desde a ultima leitura, atualiza os dados
        this->atualizaDados();
    return this->eixoZ;
}

void BMI160::calibrar(){
    Serial.println(F("Iniciando calibragem do BMI160, deixe o robo parado..."));
    delay(100);
    
    // Le valores atuais para offsets do acelerometro
    int16_t ax, ay, az, gx, gy, gz;
    getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
    
    // Armazena offsets do acelerometro (assumindo posicao horizontal)
    accelOffsetX = ax;
    accelOffsetY = ay;

    // Mede o vies (bias) do giroscopio com o FOC do proprio BMI160 e liga a
    // compensacao. (Antes so se salvavam os registradores de offset, que
    // estavam zerados depois do soft reset: o vies nunca era corrigido.)
    setGyroOffsetEnabled(false);
    autoCalibrateGyroOffset();
    setGyroOffsetEnabled(true);
    
    // Salva offsets do gyro na EEPROM
    int16_t temp;
    temp = this->getXGyroOffset();
    EEPROM.put(ENDERECO_EEPROM_BMI160, temp);
    temp = this->getYGyroOffset();
    EEPROM.put(ENDERECO_EEPROM_BMI160 + 2, temp);
    temp = this->getZGyroOffset();
    EEPROM.put(ENDERECO_EEPROM_BMI160 + 4, temp);
    
    // Salva offsets do acelerometro
    EEPROM.put(ENDERECO_EEPROM_BMI160 + 6, accelOffsetX);
    EEPROM.put(ENDERECO_EEPROM_BMI160 + 8, accelOffsetY);
    EEPROM.update(ENDERECO_EEPROM_BMI160 + 10, BMI160_MARCA_CALIBRADO);

    Serial.print(F("Vies do giro Z: "));
    Serial.print(getZGyroOffset() * 0.061, 2);
    Serial.println(F(" graus/s"));

    resetFIFO();       // descarta as amostras de antes da calibragem
    angleZ = 0;
    restoZ = 0;
    eixoZ = 0;
    Serial.println(F("Calibragem do BMI160 concluida!"));
}

void BMI160::carregaCalibracao(){
    angleZ = 0;
    restoZ = 0;
    if (EEPROM.read(ENDERECO_EEPROM_BMI160 + 10) != BMI160_MARCA_CALIBRADO) {
        // EEPROM vazia ou gravada pela versao antiga do calibrar() (offsets zerados)
        accelOffsetX = accelOffsetY = 0;
        Serial.println(F("BMI160 sem calibragem salva: rode calibrar() uma vez com o robo parado"));
        return;
    }
    // Le a EEPROM e passa os parametros de calibracao para o BMI160
    int16_t temp;
    EEPROM.get(ENDERECO_EEPROM_BMI160, temp);
    this->setXGyroOffset(temp);
    EEPROM.get(ENDERECO_EEPROM_BMI160 + 2, temp);
    this->setYGyroOffset(temp);
    EEPROM.get(ENDERECO_EEPROM_BMI160 + 4, temp);
    this->setZGyroOffset(temp);
    this->setGyroOffsetEnabled(true);
    
    // Carrega offsets do acelerometro
    EEPROM.get(ENDERECO_EEPROM_BMI160 + 6, accelOffsetX);
    EEPROM.get(ENDERECO_EEPROM_BMI160 + 8, accelOffsetY);
    resetFIFO();
}

void BMI160::resetaZ(){
    lerFIFO();         // o que ja aconteceu entra na conta antes de zerar
    angleZ = 0;
    restoZ = 0;
    eixoZ = 0;
}
