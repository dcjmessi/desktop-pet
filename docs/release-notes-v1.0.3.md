# Desktop Pet Workshop v1.0.3

`v1.0.3` brings invitation-code networking to Desktop Pet Workshop and packages the current Windows experience as a portable release.

## Highlights

- Five built-in animated desktop pets
- Nine pre-rendered accessory sets with instant switching
- Inline keyword chat and matching pet actions
- One-to-one invitation-code networking
- End-to-end encrypted chat messages
- Remote pet display and manual action synchronization
- System tray, scaling, optional desktop walking and single-instance protection

## Download and Run

1. Download `DesktopPetWorkshop-v1.0.3-win64.zip` from the Assets section below.
2. Extract the **entire** archive to a writable folder.
3. Run `DesktopPetWorkshop.exe` from the extracted folder.

Python is not required on the target computer. Do not run the EXE directly from inside the ZIP, and do not copy only the EXE because the adjacent runtime and asset files are required.

SHA-256 for the currently prepared ZIP:

```text
B64AF58FDAF674C1A256D53D971FE0AF6E7EA9F3F020AFD43AAE90A32D7B8614
```

## Verification

Before preparing this release, the following automated checks passed locally on Windows:

- Application lifecycle, pet switching, animations, accessories, keyword chat, window signals and settings
- Encrypted loopback chat and action synchronization
- End-to-end two-controller online UI flow

Public internet connectivity still depends on the selected mapping service correctly forwarding WebSocket upgrade requests. HTTPS/WSS is recommended for transport security.

## Asset License Notice

The repository's MIT License covers source code, scripts and project configuration only. Bundled pet artwork, animation frames and accessory frames are excluded. They are provided for personal learning and evaluation; this release does not grant commercial-use or redistribution rights for those assets. Verify authorization with the original creators or replace the assets before redistribution.

## Suggested Release Assets

- `DesktopPetWorkshop-v1.0.3-win64.zip`
- One selected demo video from the local `release/效果图/` folder
- SHA-256 checksum shown above

## Known Limitations

- Windows only
- Online mode currently supports two users at a time
- Both users need compatible built-in pet packs
- Real public-network behavior depends on the mapping provider and should be tested separately
