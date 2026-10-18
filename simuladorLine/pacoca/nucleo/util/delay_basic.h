// simulador: cada volta do _delay_loop_1 gasta 3 ciclos e a do _delay_loop_2 gasta 4
#include "../Arduino.h"
static inline void _delay_loop_1(uint8_t n) { sim_gasta_ciclos(3u * (n ? n : 256u)); }
static inline void _delay_loop_2(uint16_t n) { sim_gasta_ciclos(4u * (n ? n : 65536u)); }
