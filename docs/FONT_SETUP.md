# Telugu Font Setup

The production lyric style defaults to **Baloo Tammudu 2 ExtraBold**, a Telugu-specific member of the Baloo 2 family. The upstream project documents five weights and specifically identifies Baloo Tammudu 2 as the Telugu family.

The project intentionally does not bundle the TTF in the source ZIP. Run:

```bash
python scripts/install_font.py
```

The installer uses the official EkType Baloo 2 GitHub release and selects `BalooTammudu2-ExtraBold.ttf`.

A compatible system installation is also accepted through fontconfig.
