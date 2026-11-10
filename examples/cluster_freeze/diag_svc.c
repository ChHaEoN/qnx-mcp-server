/* Original diagnostics service: an idle two-thread server that nothing calls in this run. */
#include "cockpit.h"

static int chid;

static void *serve(void *unused)
{
    (void)unused;
    for (;;) {
        struct cockpit_msg msg;
        int rcvid = MsgReceive(chid, &msg, sizeof(msg), NULL);
        if (rcvid == -1) fail("diag MsgReceive");
        if (rcvid == 0) continue;
        if (MsgReply(rcvid, 0, &msg, sizeof(msg)) == -1) fail("diag MsgReply");
    }
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 2) return EXIT_FAILURE;
    alarm(SERVICE_WATCHDOG_SECONDS);
    chid = ChannelCreate(0);
    if (chid == -1) fail("diag ChannelCreate");
    start_thread(serve, NULL, NULL);
    report_ready(argv[1], chid);
    serve(NULL);
}
