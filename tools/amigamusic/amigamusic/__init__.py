"""amigamusic – mały, czysty (clean-room) zestaw do muzyki w stylu Amiga ProTracker.

Tylko numpy. Moduły:
  paula       – tabela okresów PT, kanały 8-bit, miks LRRL, filtry A500/LED
  instruments – biblioteka instrumentów (proceduralne sample 8-bit) + presety stylów
  songtext    – parser czytelnego formatu .song (wiersze, nuty, instrumenty, efekty PT)
  player      – odtwarzacz z semantyką efektów ProTrackera (tick-accurate)
  modexport   – eksport do .mod (M.K., 4 kanały, 31 sampli)
  analyze     – głośność (BS.1770 / LUFS), true peak, test szwu pętli, PNG
  cli         – `render`, `check`, `dump`, `new`, `instruments`
"""
__version__ = "1.0"
