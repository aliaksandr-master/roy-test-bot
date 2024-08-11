FROM alxemaster/basic-py312:1.0.0

COPY --chown=$USER:$USER ./poetry.lock ./pyproject.toml $PROJECT_DIR/
USER root
RUN --mount=type=cache,uid=1001,target=$HOME/.cache/pypoetry/cache $SCRIPTS_PATH/install-dependencies.sh
USER $USER
COPY --chown=$USER:$USER . $PROJECT_DIR/


CMD make app_tg_public
