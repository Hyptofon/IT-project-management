# S-02: локальний демонстраційний фрагмент прав

Мінімальний виконуваний інкремент для навчального Sprint 1: Python 3.10+
і стандартна бібліотека. Не вебсервіс, не комерційна архітектура, не SSO S-01.
Ролі зберігаються в окремому JSON-файлі; інтерактивні команди й автоматичні
тести дозволяють показати відмову та відсутність побічних змін.

## Чому цей формат достатній для першого фрагмента

Кроки 7–9 ЛР4 вимагають реального результату, який можна показати, і чесних
дат; ЛР6 задає бінарні AC, але не вимагає HTTP, UI або конкретного framework.
У репозиторії вже використовується Python для валідації. Тому CLI з guard
і тестами — найменша відтворювана демонстрація правил S-02 без нових сервісів
або продуктового вибору. Це **фрагмент**, не приймання всієї історії.

## Межі та загрози

- `T-admin`, `T-applicant`, `T-approver` — синтетичні ідентичності. `--actor`
  вибирає рольову персону, **не автентифікує** людину й не захищає від
  оператора, який може змінити локальний файл. Реальних паролів або токенів немає.
- Початковий admin — явний bootstrap fixture. Лише admin може призначати ролі;
  відсутня/невідома роль, акаунт або операція — deny за замовчуванням.
- `guarded()` перевіряє дозвіл **до** виклику callback. Заборонений callback
  не виконується; тести перевіряють і незмінність файлу.
- `probe` виконує тільки permission probe. Бронювання, погодження заявки,
  каталог і перевірка належності реальної заявки **ще не реалізовані**.
  Імена `read_own_request`/`cancel_own_request` задають рольову політику;
  вони не доводять object-level authorization або виконання S-05/S-07/S-11.
- JSON store розрахований на одного локального виконавця, не паралельних
  користувачів. Це не production authentication/security boundary.

## Правила

| Роль | Дозволені продуктові дії | Керування ролями |
| --- | --- | --- |
| applicant | search, submit_request, read_own_request, cancel_own_request | Заборонене |
| approver | approve_request | Заборонене |
| admin | edit_catalog | assign_role |
| Відсутня/невідома | Жодна | Заборонене |

Політика відповідає тестовим ролям Planning і DoR. Це не додавання нових
прав заради зручності й не твердження про реальні системи академії.

## Відтворення з кореня репозиторію

Тести не потребують мережі чи встановлення бібліотек:

```powershell
python -m unittest discover -s product_demo/roles/tests -v
```

Для демонстрації створіть **нову** власну тимчасову папку, наприклад:

```powershell
$demoDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('s02-demo-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $demoDirectory | Out-Null
$demoStore = Join-Path $demoDirectory 'accounts.json'
python -m product_demo.roles.cli --store $demoStore init
python -m product_demo.roles.cli --store $demoStore assign --actor T-admin --subject T-applicant --role applicant
python -m product_demo.roles.cli --store $demoStore assign --actor T-admin --subject T-approver --role approver
python -m product_demo.roles.cli --store $demoStore role --subject T-applicant
python -m product_demo.roles.cli --store $demoStore probe --actor T-applicant --action approve_request
# Очікуваний exit code 3: deny, callback не виконується.
python -m product_demo.roles.cli --store $demoStore probe --actor T-approver --action approve_request
# Exit code 0: guard допускає probe, не погоджує справжню заявку.
python -m product_demo.roles.cli --store $demoStore probe --actor T-approver --action edit_catalog
# Exit code 3.
python -m product_demo.roles.cli --store $demoStore probe --actor T-admin --action edit_catalog
# Exit code 0; каталогу S-11 тут немає.
```

`init` відмовляється перезаписати наявний файл. Діагностичне `role` читає
несекретну fixture-роль; це не відкритий endpoint майбутнього сервісу.

## Трасування AC і межа готовності

| AC S-02 | Що перевіряє цей фрагмент | Що лишається pending |
| --- | --- | --- |
| Admin задає три ролі; повторне читання зберігає роль | assign та перезавантаження JSON, три значення Role | Приймальна демонстрація й незалежний review |
| Applicant не погоджує/не редагує; approver погоджує, але не редагує | Guard, дозволи, deny без виклику callback і без зміни файлу | Підключення guard до реальних продуктових операцій; probe не є їх реалізацією |
| Admin редагує каталог; невідома роль дає відмову | Право edit_catalog і fail-closed перевірки | Реальна операція каталогу — залежна S-11, зараз не починається |

S-02 залишається **In progress**, S-11 не розпочата. Тести фрагмента не є
Done історії, Sprint Review, повним SC-04 або прийманням викладачем.
