/* Original front-radar service. In fault mode its front end stops after ten frames. */
#include "cockpit.h"

enum { FRAME_MS = 200, FRONTEND_LOSS_FRAME = 10 };

static pthread_mutex_t radar_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t frontend_changed = PTHREAD_COND_INITIALIZER;
static int frontend_ok = 1; /* protected by radar_lock */
static int frame_wanted;    /* protected by radar_lock */
static int lose_frontend;
static int event_coid;

/* Simulated radar front end: every 200 ms it delivers a frame if one was requested. */
static void *front_end(void *unused)
{
    (void)unused;
    for (unsigned frame = 1;; ++frame) {
        sleep_ms(FRAME_MS);
        pthread_mutex_lock(&radar_lock);
        if (lose_frontend && frame == FRONTEND_LOSS_FRAME) {
            frontend_ok = 0;
            note(35, "radar front end lost after frame %u; waiting for re-initialisation", frame);
        }
        while (!frontend_ok) pthread_cond_wait(&frontend_changed, &radar_lock);
        int deliver = frame_wanted;
        frame_wanted = 0;
        pthread_mutex_unlock(&radar_lock);
        if (deliver && MsgSendPulse(event_coid, -1, PULSE_RADAR_FRAME, (int)frame) == -1)
            fail("MsgSendPulse");
    }
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 3 || (strcmp(argv[2], "healthy") != 0 && strcmp(argv[2], "lose_frontend") != 0))
        return EXIT_FAILURE;
    alarm(SERVICE_WATCHDOG_SECONDS);
    lose_frontend = strcmp(argv[2], "lose_frontend") == 0;
    log_init("qnx_mcp_cluster_radar");

    int request_chid = ChannelCreate(0);
    if (request_chid == -1) fail("radar request ChannelCreate");
    int event_chid = ChannelCreate(_NTO_CHF_PRIVATE);
    if (event_chid == -1) fail("radar event ChannelCreate");
    event_coid = ConnectAttach(0, 0, event_chid, _NTO_SIDE_CHANNEL, 0);
    if (event_coid == -1) fail("radar event ConnectAttach");
    start_thread(front_end, NULL, NULL);
    report_ready(argv[1], request_chid);

    for (;;) {
        struct cockpit_msg msg;
        int rcvid = MsgReceive(request_chid, &msg, sizeof(msg), NULL);
        if (rcvid == -1) fail("radar request MsgReceive");
        if (rcvid == 0) continue;
        if (msg.type != GET_OBJECTS) {
            MsgError(rcvid, EINVAL);
            continue;
        }
        /* The reply is deferred until the front end delivers the next frame. */
        pthread_mutex_lock(&radar_lock);
        frame_wanted = 1;
        pthread_mutex_unlock(&radar_lock);
        note(30, "object request %u accepted; waiting for the next radar frame on channel %d",
             msg.request_id, event_chid);
        struct _pulse pulse;
        for (;;) {
            int event = MsgReceive(event_chid, &pulse, sizeof(pulse), NULL);
            if (event == -1) fail("radar event MsgReceive");
            if (event == 0 && pulse.code == PULSE_RADAR_FRAME) break;
        }
        msg.adas = ADAS_READY;
        msg.objects = 2;
        if (MsgReply(rcvid, 0, &msg, sizeof(msg)) == -1)
            note(32, "object request %u: requester no longer waiting (errno %d)", msg.request_id,
                 errno);
        else
            note(31, "object request %u answered from radar frame %d", msg.request_id,
                 pulse.value.sival_int);
    }
}
