"""Ukrainian string catalog + per-control help-text registry (FR-035, FR-037, FR-038).

Single-locale approach (no gettext/Babel): templates call `t(key)` for
labels/messages and `help_for(control_id)` for the Ukrainian text behind
every configuration control's `?` affordance. Technical identifiers
(`T3`, `-sV`, port numbers, script ids, HTTP methods) are emitted
literally in templates and never routed through this catalog.

`CONFIGURATION_CONTROL_IDS` is the contract this module is checked
against (tests/unit/test_i18n_help_coverage.py, FR-038): every id a
template references for a configuration control must have an entry in
`HELP`.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# General UI string catalog.
# ---------------------------------------------------------------------------

STRINGS: dict[str, str] = {
    "app.brand": "Milmap",
    "nav.dashboard": "Головна",
    "nav.profiles": "Профілі",
    "nav.history": "Історія",
    "nav.schedules": "Заплановані",
    "nav.configuration": "Конфігурація",
    "nav.credential_tool": "Перевірка паролів",
    "nav.reference_versions": "Довідник версій",
    "nav.signout": "Вийти",
    "login.title": "Вхід",
    "login.username": "Ім'я користувача",
    "login.password": "Пароль",
    "login.submit": "Увійти",
    "dashboard.title": "Головна",
    "dashboard.subtitle": (
        "Останні профілі виявлення та останні запуски сканування."
    ),
    "dashboard.col_profile": "Профіль",
    "dashboard.col_target": "Ціль",
    "dashboard.col_last_run": "Останній запуск",
    "dashboard.col_non_compliant": "Не відповідає",
    "dashboard.no_runs": "Завершених запусків ще немає.",
    "dashboard.run_now": "Запустити зараз",
    "dashboard.none": "Поки немає профілів із перевіркою відповідності.",
    "dashboard.view": "Переглянути",
    "dashboard.recent_profiles_title": "Останні профілі",
    "dashboard.recent_profiles_none": "Поки немає профілів. Створіть перший.",
    "dashboard.recent_scans_title": "Останні сканування",
    "dashboard.recent_scans_none": "Сканувань ще не виконано.",
    "dashboard.upcoming_schedules_title": "Найближчі заплановані завдання",
    "dashboard.upcoming_schedules_none": "Запланованих завдань немає.",
    "dashboard.compliance_na": "не застосовно",
    # Deprecated (feature 009): the browser target prompt was replaced by the
    # Scan Configuration page; no template references this key anymore. Kept as
    # a harmless no-op for one release rather than removed outright.
    "dashboard.target_required_prompt": "Вкажіть ціль для цього сканування:",
    "dashboard.target_less_hint": "Профіль без збереженої цілі",
    "profiles.title": "Профілі сканування",
    "profiles.new": "+ Новий профіль",
    "profiles.col_name": "Назва",
    "profiles.col_target": "Ціль",
    "profiles.col_ports": "Порти",
    "profiles.none": "Поки немає профілів. Створіть перший.",
    "profiles.edit": "Редагувати",
    "profiles.run_now": "Запустити",
    "profiles.duplicate": "Дублювати",
    "profiles.delete": "Видалити",
    "profiles.delete_confirm": "Видалити профіль",
    "editor.title_new": "Новий профіль",
    "editor.title_edit": "Редагування профілю",
    "editor.name": "Назва",
    "editor.description": "Опис",
    "editor.target_scope": "Ціль (хости/CIDR/діапазони через кому)",
    "editor.port_spec": "Порти",
    "editor.timing": "Швидкість сканування",
    "editor.field_open_ports": "Витягувати відкриті порти",
    "editor.field_service_version": "Витягувати версію служби/прошивки",
    "editor.compliance_version": "Перевірка актуальності версії",
    "editor.nse_scripts": "NSE-скрипти",
    "editor.command_preview": "Попередній перегляд команди",
    "editor.save": "Зберегти профіль",
    "editor.cancel": "Скасувати",
    # Feature 009 — Scan Configuration page (one-off launch step).
    "scan_config.title": "Сканування",
    "scan_config.profile": "Профіль",
    "scan_config.start_scan": "Почати сканування",
    "scan_config.target_required_hint": "Вкажіть ціль, щоб почати сканування.",
    "scan_config.name": "Назва",
    "scan_config.name_placeholder": "Необов'язково; потрібна лише для збереження як профіль",
    "scan_config.save_as_profile": "Зберегти як профіль",
    "scan_config.name_required": "Вкажіть назву, щоб зберегти профіль.",
    "scan_config.custom_scan": "Довільне сканування",
    "run.title": "Запуск сканування",
    "run.profile": "Профіль",
    "run.status": "Статус",
    "run.started": "Розпочато",
    "run.finished": "Завершено",
    "run.in_progress": "Сканування виконується…",
    "run.cancel": "Скасувати",
    "run.failed": "Запуск завершився помилкою",
    "run.no_hosts": "Хостів, що відповіли, немає.",
    "run.col_host": "Хост",
    "run.col_ports": "Відкриті порти",
    "run.col_version": "Версія служби",
    "run.col_compliance": "Відповідність",
    "run.col_nse": "Вивід NSE",
    "run.ports_all_closed": "Всі порти closed або filtered",
    # Feature 009 — results-page host selection + pivot actions.
    "run.selection_toolbar": "Дії над вибраними хостами",
    "run.selected_count": "Вибрано хостів",
    "run.select_all": "Вибрати всі",
    "run.clear_selection": "Очистити вибір",
    "run.check_credentials_selected": "Перевірити паролі на вибраних",
    "run.scan_selected_with_profile": "Сканувати вибрані профілем…",
    "run.scan_selected_go": "Сканувати вибрані",
    "run.select_invalid_version": "Вибрати хости з недійсною версією",
    "run.select_invalid_version_hint": "Додати до вибору всі хости з невідповідною версією.",
    "run.select_invalid_version_disabled": "Цей запуск не перевірявся на відповідність версії.",
    "run.expected_valid": "Очікувана чинна версія",
    "run.remediation_note": "Примітка",
    "history.title": "Історія сканування",
    "history.col_started": "Розпочато",
    "history.col_profile": "Профіль",
    "history.col_target": "Ціль",
    "history.col_status": "Статус",
    "history.col_hosts": "Хости",
    "history.none": "Сканувань ще немає.",
    "history.yes": "Так",
    "history.no": "Ні",
    "schedules.title": "Заплановані завдання",
    "schedules.col_profile": "Профіль",
    "schedules.col_recurrence": "Періодичність",
    "schedules.col_enabled": "Увімкнено",
    "schedules.col_next_run": "Наступний запуск",
    "schedules.col_last_run": "Останній запуск",
    "schedules.col_target": "Ціль",
    "schedules.col_label": "Примітка",
    "schedules.none": "Завдань ще немає. Відкрийте профіль, щоб додати.",
    "schedules.new": "+ Нове заплановане завдання",
    "schedules.label_placeholder": "Примітка",
    "schedules.target_scope": "Ціль",
    "schedules.save": "Зберегти завдання",
    "schedules.delete": "Видалити завдання",
    # Feature 005 — recurrence kinds, once/interval fields, units, statuses.
    "schedules.kind": "Тип",
    "schedules.kind_once": "Одноразово",
    "schedules.kind_interval": "Інтервал",
    "schedules.once_day": "День",
    "schedules.once_hour": "Година",
    "schedules.once_minute": "Хвилина",
    "schedules.interval_every": "Кожні",
    "schedules.interval_count": "Кількість",
    "schedules.unit_minute": "хвилина",
    "schedules.unit_hour": "година",
    "schedules.unit_day": "день",
    "schedules.unit_week": "тиждень",
    "schedules.unit_month": "місяць",
    "schedules.completed": "Виконано",
    "schedules.enabled_label": "Увімкнено",
    "schedules.edit": "Редагувати",
    "schedules.save_changes": "Зберегти зміни",
    "schedules.cancel": "Скасувати",
    "schedules.err_run_at_future": "Час запуску має бути в майбутньому.",
    "schedules.err_every_positive": "Кількість має бути цілим числом не менше 1.",
    "schedules.err_unit": "Оберіть одиницю: хвилина, година, день, тиждень або місяць.",
    "schedules.prefill_note": (
        "Заплановано зі сканування: профіль і область цілей підставлено — "
        "оберіть періодичність і збережіть (за потреби скоригуйте профіль чи ціль)."
    ),
    "history.schedule_this_scan": "Запланувати це сканування",
    "configuration.title": "Конфігурація",
    "configuration.tab_account": "Акаунт",
    "configuration.tab_library": "Бібліотека",
    "configuration.account": "Мій акаунт",
    "configuration.change_password": "Змінити пароль",
    "configuration.current_password": "Поточний пароль",
    "configuration.new_password": "Новий пароль",
    "configuration.save": "Зберегти",
    "configuration.users": "Користувачі",
    "configuration.new_user": "Новий користувач",
    "configuration.username": "Ім'я користувача",
    "configuration.role": "Роль",
    "configuration.role_admin": "Адміністратор",
    "configuration.role_operator": "Оператор",
    "configuration.status": "Статус",
    "configuration.status_active": "Активний",
    "configuration.status_disabled": "Деактивований",
    "configuration.create_user": "Створити користувача",
    "configuration.reset_password": "Скинути пароль",
    "configuration.deactivate": "Деактивувати",
    "configuration.activate": "Активувати",
    "configuration.security_settings": "Параметри безпеки",
    "configuration.password_min_length": "Мінімальна довжина пароля",
    "configuration.lockout_threshold": "Кількість спроб",
    "configuration.lockout_duration_seconds": "Тривалість блокування (с)",
    "configuration.session_idle_timeout_seconds": "Тайм-аут сесії (с)",
    "configuration.allowlist": "Список дозволених NSE-скриптів",
    "configuration.allowlist_script_id": "Ідентифікатор скрипту",
    "configuration.allowlist_description": "Опис",
    "configuration.allowlist_safety": "Категорія безпеки",
    "configuration.allowlist_expected_ports": "Очікувані порти",
    "configuration.allowlist_enabled": "Увімкнено",
    "configuration.allowlist_add": "Додати скрипт",
    "configuration.allowlist_warning_non_safe": (
        "Цей скрипт не входить до категорії \"safe\" — "
        "додавання реєструється в журналі аудиту."
    ),
    "configuration.allowlist_import_nmap": "Імпортувати всі скрипти nmap",
    "configuration.allowlist_importing": "Імпортування…",
    "configuration.allowlist_import_result": (
        "Додано: {created}, пропущено (вже є): {skipped}, усього в каталозі nmap: {total}."
    ),
    "configuration.allowlist_ports_hint": "необов'язково, залиште порожнім для будь-якого порту",
    "configuration.allowlist_ports_parse_error": "Не вдалося розпізнати порт:",
    "configuration.allowlist_ports_range_error": (
        "Діапазон занадто великий (понад 64 портів) — "
        "залиште поле порожнім, якщо скрипт підходить для будь-якого порту:"
    ),
    "credential_tool.title": "Перевірка паролів",
    "credential_tool.run_now": "Запустити",
    "credential_tool.target_scope": "Ціль",
    "credential_tool.port": "Порт",
    "credential_tool.service": "Служба",
    "credential_tool.history": "Історія перевірок",
    "credential_tool.schedule": "Запланувати",
    "credential_tool.recurrence": "Періодичність",
    "credential_tool.next_run": "Наступний запуск",
    "credential_tool.create_task": "Створити завдання",
    "credential_tool.kind": "Тип",
    "credential_tool.kind_once": "Одноразово",
    "credential_tool.kind_interval": "Інтервал",
    "credential_tool.once_day": "День",
    "credential_tool.once_hour": "Година",
    "credential_tool.once_minute": "Хвилина",
    "credential_tool.interval_every": "Кожні",
    "credential_tool.unit_minute": "хвилина",
    "credential_tool.unit_hour": "година",
    "credential_tool.unit_day": "день",
    "credential_tool.unit_week": "тиждень",
    "credential_tool.unit_month": "місяць",
    # Feature 008 — task-table columns, dictionary selector, probe-config
    # fields, result page, and run-form layout.
    "credential_tool.col_enabled": "Увімкнено",
    "credential_tool.col_next_check": "Час наступної перевірки",
    "credential_tool.schedule_this_check": "Запланувати цю перевірку",
    "credential_tool.dictionary": "Словник облікових даних",
    "credential_tool.dictionary_none": "Спершу створіть словник облікових даних для цієї служби.",
    "credential_tool.dictionary_default": "— оберіть словник —",
    "credential_tool.attempt_ceiling": "Ліміт спроб",
    "credential_tool.attempt_ceiling_hint": "Необов'язково; порожнє ⇒ розмір словника.",
    # probe_config field labels (HTTP/HTTPS form probe)
    "credential_tool.probe_title": "Параметри HTTP/HTTPS-форми (необов'язково)",
    "credential_tool.probe_login_path": "Шлях входу",
    "credential_tool.probe_method": "Метод",
    "credential_tool.probe_username_field": "Поле логіна",
    "credential_tool.probe_password_field": "Поле пароля",
    "credential_tool.probe_encoding": "Кодування",
    "credential_tool.probe_success_status": "Статуси успіху (через кому)",
    "credential_tool.probe_success_keywords": "Ключові слова успіху (через кому)",
    "credential_tool.probe_failure_status": "Статуси відмови (через кому)",
    "credential_tool.probe_failure_keywords": "Ключові слова відмови (через кому)",
    "credential_tool.probe_fingerprint_keywords": "Ключові слова сторінки входу (через кому)",
    "credential_tool.probe_csrf_name": "Ім'я CSRF-токена (приховане поле)",
    # Result page
    "credential_tool.result_title": "Результат перевірки",
    "credential_tool.result_target": "Ціль",
    "credential_tool.result_username": "Логін",
    "credential_tool.result_response": "Відповідь",
    "credential_tool.result_outcome": "Результат",
    "credential_tool.result_attempts": "Спроби",
    "credential_tool.result_matched": "Збіг",
    "credential_tool.result_matched_as": "Знайдено обліковий запис",
    "credential_tool.result_no_attempts": "Спроб не зафіксовано.",
    "credential_tool.result_ceiling": "Ліміт спроб",
    "credential_tool.result_running": "Перевірка виконується…",
    "credential_tool.result_failed": "Перевірка завершилася помилкою",
    "credential_tool.result_back": "← До інструмента",
    # Per-service credential lists (FR-036, FR-040).
    "credential_tool.creds_title": "Списки типових облікових даних",
    "credential_tool.creds_hint": (
        "Окремий перелік логінів/паролів, який перевіряється для кожної служби."
    ),
    "credential_tool.creds_vendor": "Опис / постачальник",
    "credential_tool.creds_pairs": "Облікові дані (логін:пароль, по одному на рядок)",
    "credential_tool.creds_keywords": "Ключові слова успіху (через кому)",
    "credential_tool.creds_add": "Додати список",
    "credential_tool.creds_save": "Зберегти список",
    "credential_tool.creds_none": "Списків облікових даних ще немає.",
    "credential_tool.col_vendor": "Опис / постачальник",
    "credential_tool.col_pairs": "К-сть пар",
    "common.help": "Довідка",
    "common.search_placeholder": "Пошук…",
    "common.show_archived": "Показати архівовані",
    "reference_versions.title": "Довідник чинних версій",
    "reference_versions.col_type": "Тип",
    "reference_versions.col_vendor": "Постачальник",
    "reference_versions.col_model": "Модель",
    "reference_versions.col_min_version": "Мінімальна версія",
    "reference_versions.col_note": "Примітка",
    "reference_versions.col_imported_at": "Час імпорту",
    "reference_versions.col_source": "Джерело",
    "reference_versions.source_manual": "Вручну",
    "reference_versions.source_ingested": "Імпортовано",
    "reference_versions.add": "Додати запис",
    "reference_versions.save": "Зберегти",
    "reference_versions.delete": "Видалити",
    "reference_versions.none": "Записів довідника ще немає.",
    "reference_versions.needs_review_title": "Потребує перевірки",
    "reference_versions.needs_review_suffix": " — не вдалося автоматично визначити мінімальну версію під час перенесення, перевірте вручну.",
    # V0.7 — automated version ingestion (US3, FR-014-FR-021).
    "ingestion.title": "Джерела автоматичного оновлення версій",
    "ingestion.col_vendor": "Постачальник",
    "ingestion.col_source_url": "URL джерела",
    "ingestion.col_models": "Моделі",
    "ingestion.col_last_status": "Останній імпорт",
    "ingestion.add": "Додати джерело",
    "ingestion.save": "Зберегти джерело",
    "ingestion.delete": "Видалити",
    "ingestion.none": "Джерел ще немає.",
    "ingestion.upload_bundle": "Імпортувати пакет оновлення",
    "ingestion.choose_file": "Обрати файл пакета…",
    "ingestion.preview": "Попередній перегляд",
    "ingestion.apply": "Застосувати",
    "ingestion.apply_confirm": "Застосувати попри можливе зниження версії",
    "ingestion.col_change_model": "Модель",
    "ingestion.col_change_current": "Поточна",
    "ingestion.col_change_incoming": "Нова",
    "ingestion.col_change_effect": "Дія",
    "ingestion.effect_create": "Створення",
    "ingestion.effect_update": "Оновлення",
    "ingestion.effect_failed": "Помилка джерела",
    "ingestion.downgrade_warning": "Деякі зміни знижують мінімальну версію — потрібне підтвердження.",
    "ingestion.rejected": "Пакет відхилено: цілісність не підтверджена.",
}


# ---------------------------------------------------------------------------
# Per-control help-text registry (FR-038): every configuration control id
# referenced by a template MUST have an entry here.
# ---------------------------------------------------------------------------

HELP: dict[str, str] = {
    "timing": (
        "Налаштування швидкості сканування (шаблон часових параметрів nmap "
        "T0-T5). За замовчуванням T3 — збалансована швидкість."
    ),
    "field_open_ports": (
        "Якщо увімкнено, у результатах буде перелік відкритих портів кожного хоста."
    ),
    "field_service_version": (
        "Якщо увімкнено, nmap визначає версію служби/прошивки (додає прапорець -sV)."
    ),
    "compliance_version": (
        "Звірити виявлену версію служби з локальним офлайн-довідником чинних версій."
    ),
    "nse_scripts": (
        "Виберіть NSE-скрипти з дозволеного списку, керованого адміністратором. "
        "Під час сканування буде застосовано лише обрані та дозволені скрипти."
    ),
    "port_spec": (
        "Список портів або діапазонів через кому, наприклад 22,80,443 або 5060-5062."
    ),
    "target_scope": "Хости, підмережі (CIDR) або діапазони адрес через кому.",
    "max_rate": (
        "Максимальна кількість пакетів на секунду (прискорює або сповільнює сканування)."
    ),
    "host_timeout_seconds": "Час (у секундах), після якого сканування хоста припиняється.",
    "skip_host_discovery": "Пропустити виявлення доступності хоста (прапорець -Pn nmap).",
    "service_version_intensity": "Інтенсивність визначення версії служби (0-9).",
    "password_min_length": (
        "Мінімальна довжина пароля для всіх облікових записів. "
        "Не може бути меншою за 20 символів."
    ),
    "lockout_threshold": (
        "Кількість невдалих спроб входу до тимчасового блокування облікового запису."
    ),
    "lockout_duration_seconds": (
        "Тривалість тимчасового блокування облікового запису (у секундах) "
        "після перевищення порогу."
    ),
    "session_idle_timeout_seconds": (
        "Час неактивності (у секундах), після якого сесія користувача "
        "завершується автоматично."
    ),
    "allowlist_script_id": (
        "Технічний ідентифікатор NSE-скрипту nmap (латиницею), "
        "наприклад mikrotik-routeros-version."
    ),
    "allowlist_description": "Короткий опис призначення скрипту для операторів.",
    "allowlist_safety": (
        "Категорія безпеки скрипту nmap. Додавання скрипту поза категорією \"safe\" "
        "дозволено адміністратору, але супроводжується попередженням і записом в аудит."
    ),
    "allowlist_expected_ports": (
        "Порти, на яких цей скрипт очікується (використовується для попередження "
        "про невідповідність області сканування)."
    ),
    "allowlist_enabled": "Чи доступний цей скрипт для вибору в профілях.",
    "allowlist_import_nmap": (
        "Зчитує каталог скриптів (script.db) локальної інсталяції nmap і додає "
        "кожен ще не доданий скрипт до списку — повністю офлайн, без мережевих "
        "запитів. \"safe\"/\"other\" визначається за власними категоріями nmap; "
        "уже наявні записи не перезаписуються."
    ),
    "user_role": (
        "Роль визначає права користувача: Адміністратор керує користувачами, "
        "параметрами безпеки та дозволеним списком; Оператор працює з профілями та інструментами."
    ),
    "user_status": (
        "Деактивований користувач не може увійти; його поточна сесія негайно завершується."
    ),
    "account_current_password": "Ваш поточний пароль — потрібен для підтвердження зміни.",
    "account_new_password": "Новий пароль має відповідати чинній мінімальній довжині.",
    "tool_target_scope": (
        "Явний перелік хостів, підмереж або діапазонів для перевірки "
        "облікових даних за замовчуванням."
    ),
    "tool_port": "Порт служби для перевірки облікових даних за замовчуванням.",
    "tool_service": (
        "Протокол служби, яку буде перевірено "
        "(sip, ssh, http, https, telnet, ftp або routeros-api)."
    ),
    "tool_recurrence": (
        "Періодичність автоматичного запуску цього завдання за спільним планувальником."
    ),
    "tool_overlap_policy": (
        "Що робити, якщо попередній запуск цього завдання ще не завершився: "
        "пропустити чи поставити в черергу."
    ),
    "tool_catch_up_policy": (
        "Що робити з пропущеними запусками після простою застосунку: "
        "виконати один раз чи пропустити."
    ),
}

CONFIGURATION_CONTROL_IDS: tuple[str, ...] = tuple(HELP.keys())


def t(key: str) -> str:
    """Translate a catalog key. Falls back to the key itself (never
    raises), so a missing translation degrades to a visible, debuggable
    placeholder instead of a broken page."""
    return STRINGS.get(key, key)


def help_for(control_id: str) -> str:
    """Ukrainian help text for a configuration control's `?` affordance.
    Returns an empty string for an id with no registered help (callers
    should not render the `?` affordance in that case)."""
    return HELP.get(control_id, "")
