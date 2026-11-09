/* Original QNX synchronous IPC example. Build and run manually. */
#include "demo.h"

#include <pthread.h>
#include <string.h>
#include <sys/neutrino.h>
#include <sys/wait.h>

static void *idle_receiver(void *arg)
{
    int data;
    if (MsgReceive(*(const int *)arg, &data, sizeof(data), NULL) < 0)
        fail("idle MsgReceive");
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc < 2 || argc > 3 || (argc == 3 && strcmp(argv[2], "--fixed") != 0)) {
        fprintf(stderr, "usage: %s ./peer_b [--fixed]\n", argv[0]);
        return EXIT_FAILURE;
    }
    alarm(WATCHDOG_SECONDS);
    int callback_chid = ChannelCreate(0);
    if (callback_chid < 0) fail("callback ChannelCreate");
    int idle_chid = ChannelCreate(_NTO_CHF_PRIVATE);
    if (idle_chid < 0) fail("idle ChannelCreate");
    int ready[2];
    if (pipe(ready) < 0) fail("pipe");

    char pid_arg[32], channel_arg[32], fd_arg[32];
    snprintf(pid_arg, sizeof(pid_arg), "%ld", (long)getpid());
    snprintf(channel_arg, sizeof(channel_arg), "%d", callback_chid);
    snprintf(fd_arg, sizeof(fd_arg), "%d", ready[1]);
    pid_t b = fork();
    if (b < 0) fail("fork");
    if (b == 0) {
        close(ready[0]);
        execl(argv[1], argv[1], pid_arg, channel_arg, fd_arg,
              argc == 3 ? "fixed" : "fault", (char *)NULL);
        perror("exec peer_b");
        _exit(127);
    }
    close(ready[1]);
    int b_chid;
    transfer_channel(ready[0], &b_chid, 0);
    close(ready[0]);

    pthread_t idle;
    int thread_error = pthread_create(&idle, NULL, idle_receiver, &idle_chid);
    if (thread_error != 0) {
        errno = thread_error;
        fail("pthread_create");
    }
    slog2_buffer_t log;
    phase_init(&log, "qnx_mcp_peer_a");
    int coid = ConnectAttach(0, b, b_chid, _NTO_SIDE_CHANNEL, 0);
    if (coid < 0) fail("connect to B");
    printf("A_READY a=%ld b=%ld callback_chid=%d idle_chid=%d b_chid=%d\n",
           (long)getpid(), (long)b, callback_chid, idle_chid, b_chid);
    fflush(stdout);

    phase(log, 10, "A sends request and waits for B's reply");
    int request = REQUEST, response = 0;
    if (MsgSend(coid, &request, sizeof(request), &response, sizeof(response)) < 0)
        fail("request MsgSend");
    if (response != RESPONSE) return EXIT_FAILURE;

    phase(log, 11, "A received the reply and can now receive the callback");
    int callback = 0;
    int rcvid = MsgReceive(callback_chid, &callback, sizeof(callback), NULL);
    if (rcvid < 0) fail("callback MsgReceive");
    if (callback != CALLBACK || rcvid == 0) return EXIT_FAILURE;
    int ack = ACK;
    if (MsgReply(rcvid, 0, &ack, sizeof(ack)) < 0) fail("callback MsgReply");
    int status;
    if (waitpid(b, &status, 0) != b) fail("wait for B");
    if (!WIFEXITED(status) || WEXITSTATUS(status) != EXIT_SUCCESS) return EXIT_FAILURE;
    phase(log, 12, "A and B completed the request and callback");
    puts("DEMO_OK request and callback completed");
    return EXIT_SUCCESS;
}
