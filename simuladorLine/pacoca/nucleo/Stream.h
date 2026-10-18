#ifndef SIM_STREAM_H
#define SIM_STREAM_H
#ifdef __cplusplus
#include "Arduino.h"

class Stream : public Print {
protected:
    unsigned long _timeout = 1000;
    unsigned long _startMillis = 0;

    int timedRead() {
        int c;
        _startMillis = millis();
        do {
            c = read();
            if (c >= 0) return c;
            yield();
        } while (millis() - _startMillis < _timeout);
        return -1;
    }
    int timedPeek() {
        int c;
        _startMillis = millis();
        do {
            c = peek();
            if (c >= 0) return c;
            yield();
        } while (millis() - _startMillis < _timeout);
        return -1;
    }

public:
    virtual int available() = 0;
    virtual int read() = 0;
    virtual int peek() = 0;

    void setTimeout(unsigned long timeout) { _timeout = timeout; }
    unsigned long getTimeout(void) { return _timeout; }

    virtual size_t readBytes(char *buffer, size_t length) {
        size_t count = 0;
        while (count < length) {
            int c = timedRead();
            if (c < 0) break;
            *buffer++ = (char)c;
            count++;
        }
        return count;
    }
    virtual size_t readBytes(uint8_t *buffer, size_t length) { return readBytes((char *)buffer, length); }
    size_t readBytesUntil(char terminator, char *buffer, size_t length) {
        size_t index = 0;
        while (index < length) {
            int c = timedRead();
            if (c < 0 || c == terminator) break;
            *buffer++ = (char)c;
            index++;
        }
        return index;
    }
    String readString() {
        String ret;
        int c = timedRead();
        while (c >= 0) {
            ret += (char)c;
            c = timedRead();
        }
        return ret;
    }
    String readStringUntil(char terminator) {
        String ret;
        int c = timedRead();
        while (c >= 0 && c != terminator) {
            ret += (char)c;
            c = timedRead();
        }
        return ret;
    }
    bool find(const char *target) {
        size_t len = strlen(target), idx = 0;
        if (!len) return true;
        int c;
        while ((c = timedRead()) >= 0) {
            if (c == target[idx]) {
                if (++idx >= len) return true;
            } else idx = (c == target[0]) ? 1 : 0;
        }
        return false;
    }
    long parseInt() {
        bool neg = false;
        long v = 0;
        int c = timedPeek();
        while (c >= 0 && c != '-' && !isdigit(c)) { read(); c = timedPeek(); }
        if (c < 0) return 0;
        if (c == '-') { neg = true; read(); c = timedPeek(); }
        while (c >= 0 && isdigit(c)) { v = v * 10 + (c - '0'); read(); c = timedPeek(); }
        return neg ? -v : v;
    }
    float parseFloat() {
        String t;
        int c = timedPeek();
        while (c >= 0 && c != '-' && c != '.' && !isdigit(c)) { read(); c = timedPeek(); }
        while (c >= 0 && (c == '-' || c == '.' || isdigit(c))) { t += (char)c; read(); c = timedPeek(); }
        return t.toFloat();
    }
};

#endif
#endif
