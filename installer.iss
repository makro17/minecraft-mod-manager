; MakroModManager — Inno Setup
#define AppName    "MakroModManager"
#define AppVersion "1.1.0"
#define AppExe     "MakroModManager.exe"
#define BuildDir   "dist\MakroModManager"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\MakroModManager
DisableProgramGroupPage=yes
DisableDirPage=no
CreateAppDir=yes
DirExistsWarning=no
UsePreviousAppDir=yes
OutputDir=installer_output
OutputBaseFilename=MakroModManager_setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=assets\icon.ico
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ShowLanguageDialog=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir MakroModManager"; Flags: nowait postinstall skipifsilent
