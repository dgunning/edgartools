# Recording image for EdgarTools demo clips.
#
# Built on Charm's official VHS image (bundles vhs + ttyd + ffmpeg + fonts) and
# layers in a venv with edgartools so we can record a real REPL session — real
# terminal, real Rich output — fully reproducibly, with no Homebrew on the host.
#
# Build:  docker build -t edgartools-vhs scripts/vhs
# Render: docker run --rm -e EDGAR_IDENTITY="$EDGAR_IDENTITY" \
#             -v "$PWD:/vhs" -w /vhs edgartools-vhs scripts/vhs/<tape>.tape
FROM ghcr.io/charmbracelet/vhs:latest

# Debian trixie marks the system Python as externally managed (PEP 668), so we
# install into an isolated venv rather than fighting --break-system-packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir edgartools

# Off-camera REPL prelude: identity + pre-imports + Rich display hook.
COPY pystartup.py /opt/vhs/pystartup.py
ENV PYTHONSTARTUP=/opt/vhs/pystartup.py
# Keep Rich/Python output deterministic and unbuffered for clean recording.
ENV PYTHONUNBUFFERED=1
ENV VHS_CONSOLE_WIDTH=100
