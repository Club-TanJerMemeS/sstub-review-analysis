# SStuB Review Analysis

This repository contains the implementation of a research project investigating the influence of code review practices on Simple Stupid Bugs (SStuBs) in Java projects.

## Overview

This study examines how pull request (PR) characteristics and review practices influence the introduction and fix time of SStuBs in Java projects. We analyze the relationship between PR metrics (reviewer count, size, review comments) and SStuB occurrence/resolution.

## Research Questions

- **RQ1:** How does the number of reviewers in a pull request relate to the likelihood of introducing SStuBs across different SStuB types, controlling for PR size?
- **RQ2:** Are explicit mentions of potential SStuBs in code review comments associated with faster SStuB fixes, and does this relationship vary by SStuB type?
- **RQ3:** How does PR size (in terms of lines changed and files modified) relate to the likelihood of introducing SStuBs across different SStuB types, controlling for reviewer count?
- **RQ4:** Why do certain SStuBs escape detection by automated tests, and what factors contribute to these oversights?

## Data Sources

- ManySStuBs4J dataset
- GitHub PR metadata via GrimoireLab
- Code review comments and PR metrics
- CI pipeline logs and test results

## Project Structure

```
project-root/
├── data/                        # Data directory
│   ├── raw/                    # Raw data from ManySStuBs4J
│   ├── processed/              # Processed and enriched data
│   └── analysis/               # Analysis results
├── src/                        # Source code
│   ├── data_collection/        # Data collection scripts
│   ├── preprocessing/          # Data preprocessing scripts
│   ├── analysis/              # Analysis scripts
│   └── visualization/         # Visualization scripts
├── notebooks/                 # Jupyter notebooks
└── docs/                     # Documentation
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sstub-pr-metrics.git
cd sstub-pr-metrics
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure data sources:
- Download ManySStuBs4J dataset
- Set up GrimoireLab access
- Configure GitHub API tokens

## Usage

Detailed usage instructions coming soon.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ManySStuBs4J dataset creators
- GrimoireLab development team
- All contributors and reviewers
