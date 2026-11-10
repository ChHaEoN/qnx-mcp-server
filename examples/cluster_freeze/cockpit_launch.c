/* Original supervisor: starts the cockpit services, waits for the cluster and stops the rest. */
#include <signal.h>
#include <sys/wait.h>

#include "cockpit.h"

/* Start ./program with a ready pipe and wait for the integer it reports. */
static pid_t start(const char *program, const char *a1, const char *a2, const char *a3,
                   int *ready_value)
{
    int ready[2];
    if (pipe(ready) == -1) fail("pipe");
    char fd_arg[16];
    snprintf(fd_arg, sizeof(fd_arg), "%d", ready[1]);
    pid_t pid = fork();
    if (pid == -1) fail("fork");
    if (pid == 0) {
        close(ready[0]);
        execl(program, program, fd_arg, a1, a2, a3, (char *)NULL);
        perror(program);
        _exit(127);
    }
    close(ready[1]);
    transfer_int(ready[0], ready_value, 0);
    close(ready[0]);
    return pid;
}

static void reap(pid_t pid, int *status)
{
    while (waitpid(pid, status, 0) == -1)
        if (errno != EINTR) fail("waitpid");
}

int main(int argc, char **argv)
{
    const char *mode = "fault";
    if (argc == 2 && strcmp(argv[1], "--healthy") == 0)
        mode = "healthy";
    else if (argc == 2 && strcmp(argv[1], "--fixed") == 0)
        mode = "fixed";
    else if (argc != 1) {
        fprintf(stderr, "usage: %s [--healthy | --fixed]\n", argv[0]);
        return EXIT_FAILURE;
    }
    /* Each process has its own watchdog; the supervisor outlives them to report the result. */
    alarm(LAUNCHER_WATCHDOG_SECONDS);

    int radar_chid, fusion_chid, diag_chid, display_ready;
    char radar_pid_arg[16], radar_chid_arg[16], fusion_pid_arg[16], fusion_chid_arg[16];
    pid_t radar = start("./radar_svc", strcmp(mode, "healthy") == 0 ? "healthy" : "lose_frontend",
                        NULL, NULL, &radar_chid);
    snprintf(radar_pid_arg, sizeof(radar_pid_arg), "%ld", (long)radar);
    snprintf(radar_chid_arg, sizeof(radar_chid_arg), "%d", radar_chid);
    pid_t fusion = start("./vehicle_fusion", radar_pid_arg, radar_chid_arg,
                         strcmp(mode, "fixed") == 0 ? "fixed" : "hold_lock", &fusion_chid);
    snprintf(fusion_pid_arg, sizeof(fusion_pid_arg), "%ld", (long)fusion);
    snprintf(fusion_chid_arg, sizeof(fusion_chid_arg), "%d", fusion_chid);
    pid_t diag = start("./diag_svc", NULL, NULL, NULL, &diag_chid);
    pid_t display = start("./cluster_display", fusion_pid_arg, fusion_chid_arg, NULL,
                          &display_ready);
    printf("COCKPIT_READY mode=%s launcher=%ld radar=%ld radar_chid=%d fusion=%ld "
           "fusion_chid=%d diag=%ld diag_chid=%d display=%ld\n",
           mode, (long)getpid(), (long)radar, radar_chid, (long)fusion, fusion_chid,
           (long)diag, diag_chid, (long)display);
    fflush(stdout);

    int status, ignored;
    reap(display, &status);
    pid_t services[] = {radar, fusion, diag};
    for (size_t i = 0; i < 3; ++i) kill(services[i], SIGTERM);
    for (size_t i = 0; i < 3; ++i) reap(services[i], &ignored);

    if (WIFEXITED(status) && WEXITSTATUS(status) == EXIT_SUCCESS) {
        puts("DEMO_OK cluster rendered every frame with live radar data");
        return EXIT_SUCCESS;
    }
    if (WIFEXITED(status) && WEXITSTATUS(status) == EXIT_DEGRADED) {
        puts("DEMO_OK cluster rendered every frame; ADAS shown unavailable after the radar "
             "stopped answering");
        return EXIT_SUCCESS;
    }
    if (WIFSIGNALED(status))
        printf("DEMO_HANG cluster_display stopped updating and was ended by signal %d\n",
               WTERMSIG(status));
    else
        printf("DEMO_FAILED cluster_display exited with status %d\n", WEXITSTATUS(status));
    return EXIT_FAILURE;
}
