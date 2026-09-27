## `python-glaive-100` (Glaive Python Code QA Dataset)

The [Glaive Code Assistant dataset](https://www.kaggle.com/datasets/thedevastator/glaive-python-code-qa-dataset) contains ~140k code problems and solutions designed to create intelligent Python code assistants. Structured in a QA format, this dataset contains real-world user questions worded for coding issues from the basics of data types to more complex object-oriented programming problems and features with approximately 60% being Python.

The [python-glaive-100.json](dataset_python-glaive-100.json) file contains a subset of the original dataset featuring only the questions shorter than 100 characters, cleaned, enhanced and reformatted ready to be used by NPCs to handle prompts related to Python. 

The idea is to use this dataset, originally developed to train LLMs, to provide Python programming abilities to deterministic NPCs. The sheer amount of intents and their paraphrases makes NPCs surprisingly capable of answering Python related questions.

A lot of work has been done on the original dataset using scripts and local language models:

1. The dataset has been converted to [NDF 0.0 (NPC-Forge Dataset Format)](docs/dataset.md).
2. Removed all duplicated inputs.
3. Removed non Python questions.
4. Removed questions that require code editing (optimize this code, rewrite this code).
5. Pruned inputs to a single line or a single question.
6. Removed non-ASCII characters.
7. Lowercased inputs.
8. Added input paraphrases.
9. Moved source code output to `tools` to enable context usage (save it, append it, ecc.).
10. Manual curation, cleanup and enhancement.

The resulting [dataset_python-glaive-100.json](dataset_python-glaive-100.json) contains **4042 intents and weights around 9.7MB**. 

The paraphrases generation was done using [granite-4.1 3B](https://www.ibm.com/granite/docs/models/granite4-1) and required around 8 hours of compute on an obsolete machine with 16GB of RAM, Intel i7-4790K CPU and NVIDIA GeForce GTX 1050 Ti.

### License 

The [dataset_python-glaive-100.json](dataset_python-glaive-100.json) file is licensed under [AGPL-3.0](LICENSE).

The original source dataset is licensed under [CC0 1.0 Universal (CC0 1.0)](https://creativecommons.org/publicdomain/zero/1.0/) - Public Domain Dedication
No Copyright - You can copy, modify, distribute and perform the work, even for commercial purposes, all without asking permission.
