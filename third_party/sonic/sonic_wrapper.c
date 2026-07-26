#include "sonic.h"

#if defined(_WIN32)
#define KCTTS_EXPORT __declspec(dllexport)
#else
#define KCTTS_EXPORT __attribute__((visibility("default")))
#endif

KCTTS_EXPORT sonicStream kctts_sonic_create(int sample_rate, int channels) {
  return sonicCreateStream(sample_rate, channels);
}

KCTTS_EXPORT void kctts_sonic_destroy(sonicStream stream) {
  sonicDestroyStream(stream);
}

KCTTS_EXPORT void kctts_sonic_set_speed(sonicStream stream, float speed) {
  sonicSetSpeed(stream, speed);
}

KCTTS_EXPORT int kctts_sonic_write_float(
    sonicStream stream, const float* samples, int frame_count) {
  return sonicWriteFloatToStream(stream, samples, frame_count);
}

KCTTS_EXPORT int kctts_sonic_read_float(
    sonicStream stream, float* samples, int max_frames) {
  return sonicReadFloatFromStream(stream, samples, max_frames);
}

KCTTS_EXPORT int kctts_sonic_flush(sonicStream stream) {
  return sonicFlushStream(stream);
}

KCTTS_EXPORT int kctts_sonic_available(sonicStream stream) {
  return sonicSamplesAvailable(stream);
}
