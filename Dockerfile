FROM mcr.microsoft.com/dotnet/sdk:10.0.100-noble
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y --no-install-recommends python3 python3-venv curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/word-venv
ENV PATH="/opt/word-venv/bin:${PATH}"
ENV PYTHONPATH="/opt/word-studio/src"
WORKDIR /opt/word-studio
COPY requirements.lock requirements-resolved.lock pins.json pyproject.toml LICENSE THIRD_PARTY_NOTICES.md ./
COPY sdk/ ./sdk/
COPY src/ ./src/
COPY schemas/ ./schemas/
COPY third_party/ ./third_party/
COPY ci/bootstrap.sh ci/render-bootstrap.sh ci/uno_refresh.py ./ci/
RUN bash ci/bootstrap.sh && bash ci/render-bootstrap.sh
ENTRYPOINT ["python", "/opt/word-studio/src/word_module_studio/client.py"]
