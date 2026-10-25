"""The 8 synthetic ASIC blocks this tool server serves design/CAD data for.

Independent of, and not sourced from, the sibling repo's 8 real OpenTitan `prim_*` blocks
(ai-assisted-failure-triage-gate): this project's blind-downstream role is to serve design and
CAD artifacts, not to triage simulation failures, so reusing that repo's actual block names
would blur rather than clarify the distinction. These names are plausible-but-invented silicon
IP block names, consistent with meta.json's relationship: "new".
"""

BLOCKS = [
    "aes_core",
    "uart_core",
    "spi_host",
    "i2c_target",
    "timer_core",
    "gpio_ctrl",
    "otp_ctrl",
    "flash_ctrl",
]
