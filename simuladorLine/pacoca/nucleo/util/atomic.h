// simulador: ATOMIC_BLOCK desliga as interrupções durante o bloco
#include "../Arduino.h"
static inline uint8_t __sim_atomic_ini(void) { cli(); return 1; }
#define ATOMIC_RESTORESTATE
#define ATOMIC_FORCEON
#define NONATOMIC_RESTORESTATE
#define NONATOMIC_FORCEOFF
#define ATOMIC_BLOCK(tipo) for (uint8_t __sreg_ant = SREG, __ok = __sim_atomic_ini(); __ok; __ok = 0, SREG = __sreg_ant)
#define NONATOMIC_BLOCK(tipo) for (uint8_t __sreg_ant = SREG, __ok = (sei(), 1); __ok; __ok = 0, SREG = __sreg_ant)
