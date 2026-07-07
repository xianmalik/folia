FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-mcp.txt ./
# Core build deps + MCP server + light ATS deps (pypdf/rapidfuzz/groq — the
# LLM backend; spaCy NLP fallback is left out to keep the image small, so
# JD matching in Docker needs GROQ_API_KEY).
RUN pip3 install --no-cache-dir -r requirements.txt -r requirements-mcp.txt \
    "pypdf>=3.0" "rapidfuzz>=3.0" "groq>=0.9"

COPY . .

RUN mkdir -p dist

# Default: build the PDF. For the MCP server (stdio) run instead:
#   docker run --rm -i -v "$(pwd):/app" --env-file .env folia python3 mcp/server.py
CMD ["python3", "core/scripts/build.py"]
