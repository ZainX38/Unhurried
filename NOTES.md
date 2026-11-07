# Getting Started

**Starting Project:**
```shell
mkdir unhurried && cd unhurried     # Backend
uv init --package --python 3.12     # v3.12 to ensure compatibility with all libraries used
uv add fastapi "uvicorn[standard]" numpy
uv add --dev pytest
mkdir issues, docs/adr, unhurried/endpointer, tests, eval/data, eval/results 
```

**Installing Matt Pocock skills:**
```shell
claude plugin marketplace add mattpocock/skills
claude plugin install mattpocock-skills@mattpocock --scope project
```

