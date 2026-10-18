#ifndef SIM_PRINT_H
#define SIM_PRINT_H
#ifdef __cplusplus
#include "Arduino.h"

#define DEC 10
#define HEX 16
#define OCT 8
#define BIN 2

class Print;

class Printable {
public:
    virtual ~Printable() {}
    virtual size_t printTo(Print &p) const = 0;
};

class Print {
    int write_error = 0;

protected:
    void setWriteError(int err = 1) { write_error = err; }

public:
    virtual ~Print() {}
    int getWriteError() { return write_error; }
    void clearWriteError() { setWriteError(0); }

    virtual size_t write(uint8_t c) = 0;
    size_t write(const char *str) {
        if (str == NULL) return 0;
        return write((const uint8_t *)str, strlen(str));
    }
    virtual size_t write(const uint8_t *buffer, size_t size) {
        size_t n = 0;
        while (size--) {
            if (write(*buffer++)) n++;
            else break;
        }
        return n;
    }
    size_t write(const char *buffer, size_t size) { return write((const uint8_t *)buffer, size); }
    virtual int availableForWrite() { return 0; }
    virtual void flush() {}

    size_t print(const __FlashStringHelper *f) { return write(reinterpret_cast<const char *>(f)); }
    size_t print(const String &s) { return write(s.c_str(), s.length()); }
    size_t print(const char str[]) { return write(str); }
    size_t print(char c) { return write((uint8_t)c); }
    size_t print(unsigned char b, int base = DEC) { return print((unsigned long)b, base); }
    size_t print(int n, int base = DEC) { return print((long)n, base); }
    size_t print(unsigned int n, int base = DEC) { return print((unsigned long)n, base); }
    size_t print(long n, int base = DEC) {
        if (base == 0) return write((uint8_t)n);
        if (base == 10 && n < 0) {
            size_t t = print('-');
            return t + printNumber((unsigned long)(-n), 10);
        }
        return printNumber((unsigned long)n, base);
    }
    size_t print(unsigned long n, int base = DEC) {
        if (base == 0) return write((uint8_t)n);
        return printNumber(n, base);
    }
    size_t print(long long n, int base = DEC) { return print((long)n, base); }
    size_t print(unsigned long long n, int base = DEC) { return print((unsigned long)n, base); }
    size_t print(double n, int digits = 2) { return printFloat(n, (uint8_t)digits); }
    size_t print(const Printable &x) { return x.printTo(*this); }

    size_t println(void) { return write("\r\n"); }
    template <typename T> size_t println(T v) { size_t n = print(v); return n + println(); }
    template <typename T> size_t println(T v, int b) { size_t n = print(v, b); return n + println(); }

    size_t printf(const char *fmt, ...) __attribute__((format(printf, 2, 3)));

private:
    size_t printNumber(unsigned long n, uint8_t base) {
        char buf[8 * sizeof(long) + 1];
        char *str = &buf[sizeof(buf) - 1];
        *str = '\0';
        if (base < 2) base = 10;
        do {
            char c = (char)(n % base);
            n /= base;
            *--str = c < 10 ? c + '0' : c + 'A' - 10;
        } while (n);
        return write(str);
    }
    size_t printFloat(double number, uint8_t digits) {
        // como no core do AVR (mesmos textos para nan, inf e ovf)
        if (isnan(number)) return print("nan");
        if (isinf(number)) return print("inf");
        if (number > 4294967040.0) return print("ovf");
        if (number < -4294967040.0) return print("ovf");
        size_t n = 0;
        if (number < 0.0) { n += print('-'); number = -number; }
        double rounding = 0.5;
        for (uint8_t i = 0; i < digits; ++i) rounding /= 10.0;
        number += rounding;
        unsigned long int_part = (unsigned long)number;
        double remainder = number - (double)int_part;
        n += print(int_part);
        if (digits > 0) n += print('.');
        while (digits-- > 0) {
            remainder *= 10.0;
            unsigned int toPrint = (unsigned int)(remainder);
            n += print(toPrint);
            remainder -= toPrint;
        }
        return n;
    }
};

#endif
#endif
