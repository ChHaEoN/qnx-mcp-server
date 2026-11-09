#ifndef QNX_MCP_DEMO_H
#define QNX_MCP_DEMO_H

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/slog2.h>
#include <unistd.h>

enum { REQUEST = 101, RESPONSE = 102, CALLBACK = 201, ACK = 202 };

#ifndef WATCHDOG_SECONDS
#define WATCHDOG_SECONDS 30
#endif

_Static_assert(WATCHDOG_SECONDS > 0 && WATCHDOG_SECONDS <= 900,
               "watchdog must be between 1 and 900 seconds");

static inline void fail(const char *operation)
{
    perror(operation);
    exit(EXIT_FAILURE);
}

static inline void phase_init(slog2_buffer_t *buffer, const char *name)
{
    slog2_buffer_set_config_t cfg = {0};
    cfg.buffer_set_name = name;
    cfg.num_buffers = 1;
    cfg.verbosity_level = SLOG2_INFO;
    cfg.buffer_config[0].buffer_name = "phase";
    cfg.buffer_config[0].num_pages = 1;
    if (slog2_register(&cfg, buffer, 0) == -1) fail("slog2_register");
}

static inline void phase(slog2_buffer_t buffer, unsigned short code, const char *message)
{
    if (slog2f(buffer, code, SLOG2_INFO, "%s", message) == -1) fail("slog2f");
}

static inline void transfer_channel(int fd, int *value, int writing)
{
    unsigned char *p = (unsigned char *)value;
    size_t remaining = sizeof(*value);
    while (remaining != 0) {
        ssize_t n = writing ? write(fd, p, remaining) : read(fd, p, remaining);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) {
            if (n == 0) errno = EPIPE;
            fail(writing ? "write channel handshake" : "read channel handshake");
        }
        p += n;
        remaining -= (size_t)n;
    }
}

#endif
