// String do Arduino (o suficiente para o código dos alunos), em cima do std::string
#ifndef SIM_WSTRING_H
#define SIM_WSTRING_H
#ifdef __cplusplus
#include "Arduino.h"

class __FlashStringHelper;

class String {
public:
    std::string s;

    String(const char *c = "") : s(c ? c : "") {}
    String(const __FlashStringHelper *f) : s(f ? reinterpret_cast<const char *>(f) : "") {}
    String(const String &o) = default;
    String(String &&o) = default;
    explicit String(char c) : s(1, c) {}
    explicit String(unsigned char v, unsigned char base = 10) { num((unsigned long)v, base); }
    explicit String(int v, unsigned char base = 10) { snum((long)v, base); }
    explicit String(unsigned int v, unsigned char base = 10) { num((unsigned long)v, base); }
    explicit String(long v, unsigned char base = 10) { snum(v, base); }
    explicit String(unsigned long v, unsigned char base = 10) { num(v, base); }
    explicit String(float v, unsigned char casas = 2) { dbl(v, casas); }
    explicit String(double v, unsigned char casas = 2) { dbl(v, casas); }

    String &operator=(const String &o) = default;
    String &operator=(String &&o) = default;
    String &operator=(const char *c) { s = c ? c : ""; return *this; }
    String &operator=(const __FlashStringHelper *f) { s = reinterpret_cast<const char *>(f); return *this; }

    unsigned int length() const { return (unsigned int)s.size(); }
    bool reserve(unsigned int n) { s.reserve(n); return true; }
    const char *c_str() const { return s.c_str(); }
    char *begin() { return &s[0]; }
    char *end() { return &s[0] + s.size(); }
    operator bool() const { return true; }

    bool concat(const String &o) { s += o.s; return true; }
    bool concat(const char *c) { if (c) s += c; return true; }
    bool concat(const __FlashStringHelper *f) { s += reinterpret_cast<const char *>(f); return true; }
    bool concat(char c) { s += c; return true; }
    bool concat(unsigned char v) { return concat(String(v)); }
    bool concat(int v) { return concat(String(v)); }
    bool concat(unsigned int v) { return concat(String(v)); }
    bool concat(long v) { return concat(String(v)); }
    bool concat(unsigned long v) { return concat(String(v)); }
    bool concat(float v) { return concat(String(v)); }
    bool concat(double v) { return concat(String(v)); }
    template <typename T> String &operator+=(T v) { concat(v); return *this; }

    bool equals(const String &o) const { return s == o.s; }
    bool equals(const char *c) const { return s == (c ? c : ""); }
    bool equalsIgnoreCase(const String &o) const {
        if (s.size() != o.s.size()) return false;
        for (size_t i = 0; i < s.size(); i++) if (tolower((unsigned char)s[i]) != tolower((unsigned char)o.s[i])) return false;
        return true;
    }
    int compareTo(const String &o) const { return s.compare(o.s); }
    bool operator==(const String &o) const { return s == o.s; }
    bool operator==(const char *c) const { return equals(c); }
    bool operator!=(const String &o) const { return s != o.s; }
    bool operator!=(const char *c) const { return !equals(c); }
    bool operator<(const String &o) const { return s < o.s; }
    bool operator>(const String &o) const { return s > o.s; }
    bool operator<=(const String &o) const { return s <= o.s; }
    bool operator>=(const String &o) const { return s >= o.s; }
    bool startsWith(const String &p) const { return s.compare(0, p.s.size(), p.s) == 0; }
    bool startsWith(const String &p, unsigned int off) const { return off <= s.size() && s.compare(off, p.s.size(), p.s) == 0; }
    bool endsWith(const String &p) const { return s.size() >= p.s.size() && s.compare(s.size() - p.s.size(), p.s.size(), p.s) == 0; }

    char charAt(unsigned int i) const { return i < s.size() ? s[i] : 0; }
    void setCharAt(unsigned int i, char c) { if (i < s.size()) s[i] = c; }
    char operator[](unsigned int i) const { return charAt(i); }
    char &operator[](unsigned int i) { static char lixo; if (i >= s.size()) { lixo = 0; return lixo; } return s[i]; }
    void getBytes(unsigned char *buf, unsigned int n, unsigned int idx = 0) const {
        if (!n || !buf) return;
        unsigned int k = 0;
        for (; k + 1 < n && idx + k < s.size(); k++) buf[k] = s[idx + k];
        buf[k] = 0;
    }
    void toCharArray(char *buf, unsigned int n, unsigned int idx = 0) const { getBytes((unsigned char *)buf, n, idx); }

    int indexOf(char c, unsigned int from = 0) const { size_t p = s.find(c, from); return p == std::string::npos ? -1 : (int)p; }
    int indexOf(const String &o, unsigned int from = 0) const { size_t p = s.find(o.s, from); return p == std::string::npos ? -1 : (int)p; }
    int lastIndexOf(char c) const { size_t p = s.rfind(c); return p == std::string::npos ? -1 : (int)p; }
    int lastIndexOf(char c, unsigned int from) const { size_t p = s.rfind(c, from); return p == std::string::npos ? -1 : (int)p; }
    int lastIndexOf(const String &o) const { size_t p = s.rfind(o.s); return p == std::string::npos ? -1 : (int)p; }
    String substring(unsigned int a) const { return a >= s.size() ? String() : String(s.substr(a).c_str()); }
    String substring(unsigned int a, unsigned int b) const {
        if (a > b) { unsigned int t = a; a = b; b = t; }
        if (a >= s.size()) return String();
        if (b > s.size()) b = (unsigned int)s.size();
        return String(s.substr(a, b - a).c_str());
    }
    void replace(char a, char b) { for (auto &c : s) if (c == a) c = b; }
    void replace(const String &a, const String &b) {
        if (a.s.empty()) return;
        size_t p = 0;
        while ((p = s.find(a.s, p)) != std::string::npos) { s.replace(p, a.s.size(), b.s); p += b.s.size(); }
    }
    void remove(unsigned int i) { if (i < s.size()) s.erase(i); }
    void remove(unsigned int i, unsigned int n) { if (i < s.size()) s.erase(i, n); }
    void toLowerCase() { for (auto &c : s) c = (char)tolower((unsigned char)c); }
    void toUpperCase() { for (auto &c : s) c = (char)toupper((unsigned char)c); }
    void trim() {
        size_t a = 0;
        while (a < s.size() && isspace((unsigned char)s[a])) a++;
        size_t b = s.size();
        while (b > a && isspace((unsigned char)s[b - 1])) b--;
        s = s.substr(a, b - a);
    }
    long toInt() const { return atol(s.c_str()); }
    float toFloat() const { return (float)atof(s.c_str()); }
    double toDouble() const { return atof(s.c_str()); }

private:
    void num(unsigned long v, unsigned char base) {
        if (base < 2) base = 10;
        char buf[40];
        int i = 39;
        buf[i] = 0;
        do { int d = (int)(v % base); buf[--i] = (char)(d < 10 ? '0' + d : 'a' + d - 10); v /= base; } while (v && i > 0);
        s = &buf[i];
    }
    void snum(long v, unsigned char base) {
        if (base == 10 && v < 0) { num((unsigned long)(-v), 10); s = "-" + s; }
        else num((unsigned long)v, base);
    }
    void dbl(double v, unsigned char casas) {
        char buf[64];
        snprintf(buf, sizeof buf, "%.*f", (int)casas, v);
        s = buf;
    }
};

inline String operator+(const String &a, const String &b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, const char *b) { String r(a); r.concat(b); return r; }
inline String operator+(const char *a, const String &b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, const __FlashStringHelper *b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, char b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, unsigned char b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, int b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, unsigned int b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, long b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, unsigned long b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, float b) { String r(a); r.concat(b); return r; }
inline String operator+(const String &a, double b) { String r(a); r.concat(b); return r; }

#endif
#endif
