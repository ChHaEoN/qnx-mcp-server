/* Original instrument-cluster client: renders a text panel every 500 ms and polls telltales. */
#include "cockpit.h"

enum { FRAMES = 12, REFRESH_MS = 500 };

static int fusion_pid, fusion_chid;
static volatile int stop_telltales;
static int degraded;

static int connect_fusion(void)
{
    int coid = ConnectAttach(0, fusion_pid, fusion_chid, _NTO_SIDE_CHANNEL, 0);
    if (coid == -1) fail("connect to vehicle_fusion");
    return coid;
}

static int ask(int coid, uint16_t type, uint32_t id, struct cockpit_msg *reply)
{
    struct cockpit_msg msg = {.type = type, .request_id = id};
    return MsgSend(coid, &msg, sizeof(msg), reply, sizeof(*reply));
}

static void render(unsigned frame, const struct cockpit_msg *s)
{
    char adas[32];
    if (s->adas == ADAS_READY)
        snprintf(adas, sizeof(adas), "FCW ready, %d objects", (int)s->objects);
    else if (s->adas == ADAS_STARTING)
        snprintf(adas, sizeof(adas), "FCW starting");
    else
        snprintf(adas, sizeof(adas), "FCW UNAVAILABLE");
    printf("+------------------ CLUSTER frame %2u ------------------+\n"
           "|  SPEED %3d km/h   GEAR %c   ADAS %-21s|\n"
           "+------------------------------------------------------+\n",
           frame, (int)s->speed_kph, (char)s->gear, adas);
    fflush(stdout);
}

static void *panel(void *unused)
{
    (void)unused;
    int coid = connect_fusion();
    for (unsigned frame = 1; frame <= FRAMES; ++frame) {
        struct cockpit_msg state;
        uint32_t id = 1000 + frame;
        note(10, "panel request %u sent to vehicle_fusion", id);
        if (ask(coid, GET_PANEL, id, &state) == -1) fail("panel MsgSend");
        note(11, "panel request %u answered; frame %u rendered", id, frame);
        degraded |= state.adas == ADAS_UNAVAILABLE;
        render(frame, &state);
        sleep_ms(REFRESH_MS);
    }
    return NULL;
}

static void *telltales(void *unused)
{
    (void)unused;
    int coid = connect_fusion();
    for (uint32_t id = 2001; !stop_telltales; ++id) {
        struct cockpit_msg state;
        if (ask(coid, GET_TELLTALES, id, &state) == -1) fail("telltale MsgSend");
        sleep_ms(REFRESH_MS);
    }
    return NULL;
}

int main(int argc, char **argv)
{
    if (argc != 4) return EXIT_FAILURE;
    alarm(WATCHDOG_SECONDS);
    fusion_pid = number(argv[2]);
    fusion_chid = number(argv[3]);
    log_init("qnx_mcp_cluster_display");
    report_ready(argv[1], 0);

    pthread_t panel_thread, telltale_thread;
    start_thread(panel, NULL, &panel_thread);
    start_thread(telltales, NULL, &telltale_thread);
    int error = pthread_join(panel_thread, NULL);
    if (error == 0) {
        stop_telltales = 1;
        error = pthread_join(telltale_thread, NULL);
    }
    if (error != 0) {
        errno = error;
        fail("pthread_join");
    }
    return degraded ? EXIT_DEGRADED : EXIT_SUCCESS;
}
