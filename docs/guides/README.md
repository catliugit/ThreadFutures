# Thread Futures: step-by-step guides

Each built part of Thread Futures explained from the ground up: the question it answers, the pipeline step by step with real code from this repo, every concept from scratch, the real results, what went wrong, honest limits, how to run it, and a glossary.

## What's in the set

| File | Part | Data label |
|---|---|---|
| [01_offcut_forecasting_step_by_step.md](01_offcut_forecasting_step_by_step.md) | Offcut forecasting | Simulated cutting runs |
| [02_analytics_engineering_step_by_step.md](02_analytics_engineering_step_by_step.md) | Analytics engineering (dbt + DuckDB) | Real open retail data |
| [03_merchandising_analytics_step_by_step.md](03_merchandising_analytics_step_by_step.md) | Merchandising analytics | Real open retail data |
| [04_stall_risk_model_step_by_step.md](04_stall_risk_model_step_by_step.md) | Stall-risk model | Real open retail data |
| [05_experimentation_step_by_step.md](05_experimentation_step_by_step.md) | Experimentation and causal analysis | Real data (markdowns) + simulated pilot |
| [06_model_monitoring_step_by_step.md](06_model_monitoring_step_by_step.md) | Model monitoring | Real open retail data |
| [07_regulation_search_step_by_step.md](07_regulation_search_step_by_step.md) | Regulation search | Retrieval prototype over real EU law text |
| [08_purchase_order_agent_step_by_step.md](08_purchase_order_agent_step_by_step.md) | Purchase-order agent | Prototype |
| [09_api_service_step_by_step.md](09_api_service_step_by_step.md) | API service | Prototype |
| [10_ci_and_docker_step_by_step.md](10_ci_and_docker_step_by_step.md) | CI and Docker build | Infrastructure |
| [11_to_17_planned_step_by_step.md](11_to_17_planned_step_by_step.md) | Parts 11 to 17 | **PLANNED, not built** |

## Concept index

Concept, then the file that explains it best (other files that use it in brackets).

### Data and analytics engineering
| Concept | File |
|---|---|
| Medallion layout (bronze, silver, gold) | 02 (01) |
| Data contracts | 01 (02) |
| dbt models, materialisation, `ref()`, DAG | 02 |
| dbt sources and `var()` | 02 (planned 13) |
| dbt generic and singular tests, custom test macros | 02 (03) |
| Reconciliation test | 02 |
| Semantic layer, MetricFlow, entities, measures, metrics, time spine | 02 (planned 11) |
| Star schema, dimension and fact tables, grain | 02 |
| DuckDB | 02 |
| Parquet | 02 |
| Left-censoring | 02 (04) |
| Window functions, rolling averages, CTEs, Jinja | 03 |
| Dense vs sparse time series (zero weeks) | 03 (04) |
| `FILTER (WHERE ...)` aggregates | 04 |

### Merchandising
| Concept | File |
|---|---|
| ABC classification, Pareto | 03 |
| XYZ classification | 03 |
| Coefficient of variation | 03 |
| Sales velocity, velocity ratio | 03 |
| Sell-through and weeks of cover (and why not used) | 03 |
| Markdown depth, list price as mode of small orders | 02, 03 |
| Return rate | 03 (02) |
| Launch cohorts | 03 (05) |

### Machine learning
| Concept | File |
|---|---|
| Simulation from first principles | 01 |
| Quantile regression, pinball loss | 01 |
| P10 / P50 / P90, interval coverage, quantile crossing | 01 |
| Gradient boosting (regression and classification), trees, hyperparameters | 01, 04 |
| One-hot encoding | 01 |
| Train/test split vs time-based split | 01, 04 |
| Data leakage, censoring leakage | 01, 04 |
| Baselines | 01, 04 |
| MAE, MAPE, within ±15%, bias | 01 |
| Base rate | 04 |
| ROC AUC vs PR AUC | 04 (06) |
| Precision at top k | 04 |
| Calibration, Brier score | 04, 06 (planned 15) |
| Feature importance | 04 |
| MLflow tracking and model registry, joblib, skops | 04 |
| Float32 thresholds, export parity tests | 01 (04, 09) |

### Experimentation and causal inference
| Concept | File |
|---|---|
| Correlation vs causation, observational vs randomised | 05 |
| Difference-in-differences, stacked DiD | 05 |
| Parallel trends, placebo test, pre-trend, upper bound | 05 |
| Matched controls, fixed effects | 05 |
| Clustered standard errors | 05 |
| Log outcomes as percentage effects | 05 |
| Confidence intervals, p-values | 05 |
| Power analysis, effect size (Cohen's d), alpha, power | 05 |
| Welch t-test | 05 |
| Bootstrap confidence interval | 05 |

### Monitoring
| Concept | File |
|---|---|
| Data drift vs concept drift | 06 |
| PSI (Population Stability Index) | 06 |
| KS test | 06 |
| Ranking vs calibration by period | 06 |
| Alert thresholds, alert fatigue | 06 |
| Static HTML reports | 06 |

### Search and language models
| Concept | File |
|---|---|
| Tokenisation, stop words, stemming | 07 |
| TF-IDF, cosine similarity | 07 |
| BM25 (k1, b) | 07 |
| hit@k, MRR, evaluation sets | 07 |
| Retrieval-augmented generation (RAG), hallucination | 07 |
| Citation checking | 07 |
| Embeddings, hybrid search (not yet used) | 07 |
| Tool use / function calling, agents, agent loop | 08 |
| System prompts, structured extraction, flagged assumptions | 08 |
| Tool errors as feedback | 08 |
| Hard constraints then weighted scoring (recycler matching) | 08 |
| Environment variables, `.env` and secrets | 08 (10) |

### Software and deployment
| Concept | File |
|---|---|
| REST, HTTP methods, status codes (422) | 09 |
| FastAPI, Pydantic validation, `Literal`, `Field` | 09 |
| Health checks, versioned endpoints | 09 (10) |
| pytest, TestClient, unit vs integration tests | 09 |
| CI, GitHub Actions (workflow, job, step, runner, `needs`) | 10 |
| Pinned dependencies | 10 |
| Docker image vs container, Dockerfile layers, non-root user, HEALTHCHECK | 10 |
| Smoke tests | 10 |
| Container registry, CD | 10 (planned 17) |

### Planned (not built)
| Concept | File |
|---|---|
| DAX, filter context, BI data models | 11_to_17 (part 11) |
| Cohort retention, churn, RFM, k-means, LTV, BG/NBD | 11_to_17 (part 12) |
| Cloud warehouses, dbt targets and adapters, SQL dialects | 11_to_17 (part 13) |
| Spark, lazy evaluation, shuffles, Delta Lake | 11_to_17 (part 14) |
| Seasonal features, Platt scaling, isotonic regression, reliability diagrams | 11_to_17 (part 15) |
| Elasticity, Bayesian inference, partial pooling, MCMC, credible intervals | 11_to_17 (part 16) |
| Azure Container Apps, ingress, scale to zero, revisions | 11_to_17 (part 17) |
