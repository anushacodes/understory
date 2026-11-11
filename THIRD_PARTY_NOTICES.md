# Third-party notices

The UI uses assets extracted from the user-supplied `Understory.html`. The original reference remains unchanged. Font notices are shipped with the frontend:

- Instrument Serif: [OFL notice](frontend/public/licenses/instrumentserif-OFL.txt), [upstream](https://github.com/Instrument/instrument-serif).
- Inter: [OFL notice](frontend/public/licenses/inter-OFL.txt), [upstream](https://github.com/rsms/inter).
- JetBrains Mono: [OFL notice](frontend/public/licenses/jetbrainsmono-OFL.txt), [upstream](https://github.com/JetBrains/JetBrainsMono).

The meadow image is the supplied reference asset; this project does not claim authorship or establish redistribution rights beyond the user's supplied design context. Verify image provenance before public redistribution.

The real import check reads **Pallets / ItsDangerous 2.2.0**, commit `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd`, under the [BSD-3-Clause license](https://github.com/pallets/itsdangerous/blob/096c8d42545d3b68ea21a4f890fb2b2d8979c0bd/LICENSE.txt). Its source is downloaded into the local database, not vendored or executed in this repository. The committed report records identity and coverage. Retain upstream notices when distributing source exports.

The local embedding model is [BAAI/bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5); downloaded model assets remain in the ignored local cache. Dependency versions are recorded in `uv.lock` and `frontend/package-lock.json`; their respective upstream licenses continue to apply.

This private project does not grant a new redistribution license for the complete application or supplied design reference.
