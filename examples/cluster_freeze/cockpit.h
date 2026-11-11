/* Shared helpers for the original instrument-cluster sample. Build and run manually. */
#ifndef QNX_MCP_COCKPIT_H
#define QNX_MCP_COCKPIT_H

#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/neutrino.h>
#include <sys/slog2.h>
#include <time.h>
#include <unistd.h>

#ifndef WATCHDOG_SECONDS
#define WATCHDOG_SECONDS 30
#endif

_Static_assert(WATCHDOG_SECONDS > 0 && WATCHDOG_SECONDS <= 900,
               "watchdog must be between 1 and 900 seconds");

/* The display's watchdog ends a frozen run first; services and the launcher outlive it. */
#define SERVICE_WATCHDOG_SECONDS (WATCHDOG_SECONDS + 3)
#define LAUNCHER_WATCHDOG_SECONDS (WATCHDOG_SECONDS + 5)

enum cockpit_type { GET_PANEL = 0x4301, GET_TELLTALES = 0x4302, GET_OBJECTS = 0x4303 };
enum adas_state { ADAS_READY = 0, ADAS_UNAVAILABLE = 1, ADAS_STARTING = 2 };
enum { PULSE_RADAR_FRAME = _PULSE_CODE_MINAVAIL + 1, EXIT_DEGRADED = 10 };

struct cockpit_msg {
    uint16_t type;
    uint16_t gear;
    uint32_t request_id;
    int32_t speed_kph;
    int32_t adas;
    int32_t objects;
};

static slog2_buffer_t phase_log;

static inline void fail(const char *operation)
{
    perror(operation);
    exit(EXIT_FAILURE);
}

/* One buffer set per stream, so a buffer-set filter is not flooded by heartbeats. */
static inline slog2_buffer_t register_log(const char *buffer_set, const char *buffer_name)
{
    slog2_buffer_set_config_t cfg = {0};
    slog2_buffer_t buffer;
    cfg.buffer_set_name = buffer_set;
    cfg.num_buffers = 1;
    cfg.verbosity_level = SLOG2_INFO;
    cfg.buffer_config[0].buffer_name = buffer_name;
    cfg.buffer_config[0].num_pages = 1;
    if (slog2_register(&cfg, &buffer, 0) == -1) fail("slog2_register");
    return buffer;
}

static inline void log_init(const char *buffer_set)
{
    phase_log = register_log(buffer_set, "phase");
}

/* Phase markers carry request IDs so separate processes can be correlated.
 * Faults use SLOG2_WARNING so a severity filter finds them among the INFO markers. */
#define note_at(severity, code, ...)                                        \
    do {                                                                    \
        if (slog2f(phase_log, (code), (severity), __VA_ARGS__) == -1)       \
            fail("slog2f");                                                 \
    } while (0)
#define note(code, ...) note_at(SLOG2_INFO, code, __VA_ARGS__)
#define warn_note(code, ...) note_at(SLOG2_WARNING, code, __VA_ARGS__)

static inline int number(const char *text)
{
    char *end;
    errno = 0;
    long n = strtol(text, &end, 10);
    if (errno || text == end || *end || n < 0 || n > INT_MAX) {
        fprintf(stderr, "invalid numeric argument\n");
        exit(EXIT_FAILURE);
    }
    return (int)n;
}

static inline void transfer_int(int fd, int *value, int writing)
{
    unsigned char *p = (unsigned char *)value;
    size_t remaining = sizeof(*value);
    while (remaining != 0) {
        ssize_t n = writing ? write(fd, p, remaining) : read(fd, p, remaining);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) {
            if (n == 0) errno = EPIPE;
            fail(writing ? "write ready value" : "read ready value");
        }
        p += n;
        remaining -= (size_t)n;
    }
}

/* Tell the launcher that this service is ready, passing its request channel. */
static inline void report_ready(const char *fd_text, int value)
{
    int fd = number(fd_text);
    if (fd <= STDERR_FILENO) fail("ready descriptor");
    transfer_int(fd, &value, 1);
    close(fd);
}

static inline void sleep_ms(long ms)
{
    struct timespec t = {ms / 1000, (ms % 1000) * 1000000L};
    while (nanosleep(&t, &t) == -1 && errno == EINTR) {
    }
}

static inline void start_thread(void *(*body)(void *), void *arg, pthread_t *out)
{
    pthread_t thread;
    int error = pthread_create(&thread, NULL, body, arg);
    if (error != 0) {
        errno = error;
        fail("pthread_create");
    }
    if (out != NULL) *out = thread;
}

#endif
