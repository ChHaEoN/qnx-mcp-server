/* Original vehicle-state fusion service. Default mode holds state_lock across a radar call. */
#include "cockpit.h"

static pthread_mutex_t state_lock = PTHREAD_MUTEX_INITIALIZER;
static int speed_kph = 48;          /* protected by state_lock */
static int adas = ADAS_STARTING;    /* protected by state_lock */
static int objects;                 /* protected by state_lock */
static int radar_coid;
static slog2_buffer_t heartbeat_log;

static int request_objects(uint32_t id, struct cockpit_msg *reply, const uint64_t *deadline_ns)
{
    struct cockpit_msg request = {.type = GET_OBJECTS, .request_id = id};
    if (deadline_ns != NULL &&
        TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_SEND | _NTO_TIMEOUT_REPLY, NULL,
                     deadline_ns, NULL) == -1)
        fail("TimerTimeout");
    return MsgSend(radar_coid, &request, sizeof(request), reply, sizeof(*reply));
}

/* Default mode: the radar call has no deadline and is made while state_lock is held. */
static void sync_radar_holding_lock(uint32_t id)
{
    struct cockpit_msg reply;
    pthread_mutex_lock(&state_lock);
    note(20, "radar object request %u sent while holding state_lock", id);
    if (request_objects(id, &reply, NULL) == -1) fail("radar MsgSend");
    adas = reply.adas;
    objects = reply.objects;
    pthread_mutex_unlock(&state_lock);
    note(21, "radar object request %u answered", id);
}

/* Fixed mode: release state_lock before the call, bound the wait and degrade on timeout. */
static void sync_radar_with_deadline(uint32_t id)
{
    static const uint64_t deadline_ns = 2000000000ULL;
    struct cockpit_msg reply;
    note(22, "radar object request %u sent with a 2 s deadline", id);
    int rc = request_objects(id, &reply, &deadline_ns);
    int saved = errno;
    if (rc == -1 && saved != ETIMEDOUT) {
        errno = saved;
        fail("radar MsgSend");
    }
    pthread_mutex_lock(&state_lock);
    adas = rc == -1 ? ADAS_UNAVAILABLE : reply.adas;
    objects = rc == -1 ? 0 : reply.objects;
    pthread_mutex_unlock(&state_lock);
    if (rc == -1)
        warn_note(23, "radar object request %u timed out; ADAS marked unavailable", id);
    else
        note(21, "radar object request %u answered", id);
}

static void *radar_sync(void *arg)
{
    int fixed = *(const int *)arg;
    for (uint32_t id = 501;; ++id) {
        if (fixed)
            sync_radar_with_deadline(id);
        else
            sync_radar_holding_lock(id);
        sleep_ms(500);
    }
    return NULL;
}

/* Liveness only: it never takes state_lock, so it keeps running during a freeze. */
static void *heartbeat(void *unused)
{
    (void)unused;
    for (uint32_t n = 1;; ++n) {
        if (slog2f(heartbeat_log, 50, SLOG2_INFO, "heartbeat %u: vehicle_fusion alive", n) == -1)
            fail("slog2f");
        sleep_ms(1000);
    }
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 5 || (strcmp(argv[4], "hold_lock") != 0 && strcmp(argv[4], "fixed") != 0))
        return EXIT_FAILURE;
    alarm(SERVICE_WATCHDOG_SECONDS);
    int radar_pid = number(argv[2]);
    int radar_chid = number(argv[3]);
    static int fixed;
    fixed = strcmp(argv[4], "fixed") == 0;
    log_init("qnx_mcp_cluster_fusion");
    heartbeat_log = register_log("qnx_mcp_cluster_heartbeat", "heartbeat");

    radar_coid = ConnectAttach(0, radar_pid, radar_chid, _NTO_SIDE_CHANNEL, 0);
    if (radar_coid == -1) fail("connect to radar_svc");
    int chid = ChannelCreate(0);
    if (chid == -1) fail("fusion ChannelCreate");
    start_thread(radar_sync, &fixed, NULL);
    start_thread(heartbeat, NULL, NULL);
    report_ready(argv[1], chid);

    for (;;) {
        struct cockpit_msg msg;
        int rcvid = MsgReceive(chid, &msg, sizeof(msg), NULL);
        if (rcvid == -1) fail("fusion MsgReceive");
        if (rcvid == 0) continue;
        if (msg.type != GET_PANEL && msg.type != GET_TELLTALES) {
            MsgError(rcvid, EINVAL);
            continue;
        }
        const char *label = msg.type == GET_PANEL ? "panel" : "telltale";
        note(40, "%s request %u received; waiting for state_lock", label, msg.request_id);
        pthread_mutex_lock(&state_lock);
        if (msg.type == GET_PANEL && speed_kph < 60) ++speed_kph;
        msg.speed_kph = speed_kph;
        msg.gear = 'D';
        msg.adas = adas;
        msg.objects = objects;
        pthread_mutex_unlock(&state_lock);
        if (MsgReply(rcvid, 0, &msg, sizeof(msg)) == -1) fail("fusion MsgReply");
        note(41, "%s request %u answered", label, msg.request_id);
    }
}
