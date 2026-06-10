"""Constantes para chaves do st.session_state."""

# Controle de ciclo de vida
SNAPSHOT_DONE = "snapshot_done"

# Modo privacidade — oculta valores monetários na UI
PRIVACY_MODE = "privacy_mode"

# Mensagens flash (exibidas uma vez após rerun)
SUCCESS_MSG = "success_message"
ERROR_MSG = "error_message"

# Estado de formulários
PORTFOLIO_FORM_OPEN = "portfolio_form_open"
EDIT_ASSET_ID = "edit_asset_id"
GOAL_FORM_OPEN = "goal_form_open"
EDIT_GOAL_ID = "edit_goal_id"

# Estado de confirmações destrutivas
CONFIRM_DELETE_TX_ID = "confirm_delete_tx_id"
CONFIRM_DEACTIVATE_ASSET_ID = "confirm_deactivate_asset_id"
CONFIRM_DEACTIVATE_GOAL_ID = "confirm_deactivate_goal_id"
CONFIRM_REACTIVATE_ASSET_ID = "confirm_reactivate_asset_id"

# Filtros de página
TX_SELECTED_ASSET_ID = "tx_selected_asset_id"
HISTORY_PERIOD = "history_period"
GOALS_EXPANDED = "goals_expanded"

# Configurações — fluxo de criação de ativo
SETTINGS_ASSET_STEP = "settings_asset_step"

# Importação de dados
IMPORT_PARSED_ROWS = "import_parsed_rows"   # list[ImportTransaction]
IMPORT_PREVIEW = "import_preview"           # ImportResult
IMPORT_FILE_HASH = "import_file_hash"       # str — SHA256 do arquivo
IMPORT_FILE_NAME = "import_file_name"       # str | None — nome original do arquivo
