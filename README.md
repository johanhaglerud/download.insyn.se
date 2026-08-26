# download.insyn.se

Repot bygger automatiskt ett sökbart index över filer under
<https://download.insyn.se/Insyn/Bruksanvisning/>.

- `manual-index.md` är avsett för läsning i GitHub.
- `manual-index.json` är avsett för programmatisk sökning och vidare bearbetning.
- `scripts/build_index.py` skannar arkivet rekursivt med enbart Pythons standardbibliotek.

GitHub Actions kör indexeringen varje söndag samt när arbetsflödet startas manuellt.
En ny commit skapas endast när någon av indexfilerna faktiskt har ändrats.

## Köra lokalt

```text
python scripts/build_index.py
```
