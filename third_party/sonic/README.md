# Sonic DSP

Vendored from [waywardgeek/sonic](https://github.com/waywardgeek/sonic) at commit `b93885dcb70aae50c6f76b0fe4e0868f029a077e`.

`sonic.c` and `sonic.h` are unmodified upstream files. Sonic is designed for real-time speech-rate changes and is distributed under the Apache License 2.0; see `LICENSE`.

`sonic_wrapper.c` is project-owned glue that exposes an explicit shared-library ABI for Python `ctypes`, including Windows DLL exports.
