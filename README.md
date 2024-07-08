# vega-versioning-workflow
> A simple workflow that updates the semantic version of packaging related files and the label on a push commit based on 
> the hashtags included in the commit message.

## About 
This workflow leverages the [vega-packaging](https://github.com/vegastyle/vega-packaging) **update_semantic_version** cli command to update the semantic version of 
a repository based on packaging related files that it has.

It will also update the semantic version of those same files match, so they match and update the label as well.

## Features
Version 0.1.0 of this workflow uses [vega-packaging](https://github.com/vegastyle/vega-packaging)v0.2.0 .

When ran it will perform the following operations: 
1. Update the semantic revision of the pyproject.toml file if available
2. Update CHANGELOG.md with the contents from the commit message and the latest semantic revision. Creates the file if
it doesn't exist.
3. Adds a semantic version label to the new commit with the updated files.  

## How To Use
Follow the instructions on [How to Setup Reusable Workflows](https://docs.github.com/en/actions/using-workflows/reusing-workflows#calling-a-reusable-workflow).

### Example
A simple example of a workflow on 
```yaml
name: Workflows to call when push command is detecte on the repo

on: push

jobs:
  update-semantic_version:
    uses: vegastyle/vega-versioning-workflow/.github/workflows/update_version_workflow.yml@v0.0.2
```
