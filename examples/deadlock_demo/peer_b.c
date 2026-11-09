/* Original peer. Fault mode sends a callback while A is waiting for its reply. */
#include "demo.h"

#include <limits.h>
#include <string.h>
#include <sys/neutrino.h>

static int number(const char *text)
{
    char *end;
    errno = 0;
    long n = strtol(text, &end, 10);
    if (errno || text == end || *end || n < 0 || n > INT_MAX) {
        fprintf(stderr, "invalid numeric handshake argument\n");
        exit(EXIT_FAILURE);
    }
    return (int)n;
}

int main(int argc, char **argv)
{
    if (argc != 5 || (strcmp(argv[4], "fixed") != 0 && strcmp(argv[4], "fault") != 0))
        return EXIT_FAILURE;
    alarm(WATCHDOG_SECONDS);
    int a_pid = number(argv[1]);
    int a_chid = number(argv[2]);
    int ready_fd = number(argv[3]);
    int fixed = strcmp(argv[4], "fixed") == 0;
    if (a_pid <= 1 || ready_fd <= STDERR_FILENO) return EXIT_FAILURE;

    int chid = ChannelCreate(0);
    if (chid < 0) fail("B ChannelCreate");
    slog2_buffer_t log;
    phase_init(&log, "qnx_mcp_peer_b");
    transfer_channel(ready_fd, &chid, 1);
    close(ready_fd);
    int request = 0;
    int rcvid = MsgReceive(chid, &request, sizeof(request), NULL);
    if (rcvid < 0) fail("request MsgReceive");
    if (request != REQUEST || rcvid == 0) return EXIT_FAILURE;

    int response = RESPONSE;
    if (fixed) {
        phase(log, 20, "B replies to A before making a callback");
        if (MsgReply(rcvid, 0, &response, sizeof(response)) < 0) fail("early MsgReply");
    } else {
        phase(log, 21, "B attempts a synchronous callback before replying to A");
    }
    int coid = ConnectAttach(0, a_pid, a_chid, _NTO_SIDE_CHANNEL, 0);
    if (coid < 0) fail("connect to A");
    int callback = CALLBACK, ack = 0;
    if (MsgSend(coid, &callback, sizeof(callback), &ack, sizeof(ack)) < 0)
        fail("callback MsgSend");
    if (ack != ACK) return EXIT_FAILURE;
    if (!fixed && MsgReply(rcvid, 0, &response, sizeof(response)) < 0) fail("late MsgReply");
    phase(log, 22, "B received the callback acknowledgement");
    return EXIT_SUCCESS;
}
