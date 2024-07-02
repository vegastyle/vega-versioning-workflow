# vega-versioning-workflow
> A simple workflow that updates the semantic version of a push commit based on the hashtags included in the message.

The changelog format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This workflow uses the update_semantic_version cli from vega-package to update packaging related files on the root of 
the repository.

## Steps
These are the steps that the workflow takes

* Checks the commit message
* Obtains the current semantic version from the **pyproject.toml** if available or the **CHANGELOG.md** file .
  * *Note:* When using a pyproject.toml file, a semantic version is expected to be found. 
  * The pyproject.toml file will be ignored if the value is set to dynamic
* The CHANGELOG.md file is created or updated with the commit message
* The new commit is tagged with the semantic version