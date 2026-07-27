def create_offline_pipeline(
    model_class,
    pipeline_class,
    *,
    repo_id,
    config_path,
    model_path,
):
    """Build an offline Kokoro pipeline with inference-only model behavior."""
    # KPipeline only calls eval() when it constructs the model itself. The app
    # passes a preloaded model, so disable training-time dropout explicitly.
    model = model_class(
        repo_id=repo_id,
        config=config_path,
        model=model_path,
    ).eval()
    return pipeline_class(lang_code="a", repo_id=repo_id, model=model)
