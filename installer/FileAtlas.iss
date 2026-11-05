; Build with scripts/build_installer.py. Application data is never uninstalled.
[Setup]
AppId={{7FC02EDA-5574-453B-B31A-5C575352EADC}
AppName=FileAtlas
AppVersion={#AppVersion}
AppPublisher=FileAtlas contributors
AppPublisherURL=https://github.com/AHuaWinliver/FileAtlas
DefaultDirName={localappdata}\Programs\FileAtlas
DefaultGroupName=FileAtlas
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#OutputRoot}
OutputBaseFilename=FileAtlas-{#AppVersion}-Setup
SourceDir={#PackageRoot}
SetupIconFile={#PackageRoot}\assets\app-icon.ico
UninstallDisplayIcon={app}\FileAtlas.exe
LicenseFile={#PackageRoot}\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists(AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl")
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FileAtlas"; Filename: "{app}\FileAtlas.exe"
Name: "{autodesktop}\FileAtlas"; Filename: "{app}\FileAtlas.exe"; Tasks: desktopicon
Name: "{autoprograms}\FileAtlas User Guide"; Filename: "{app}\docs\QUICK_START.html"

[Run]
Filename: "{app}\FileAtlas.exe"; Description: "Launch FileAtlas"; Flags: nowait postinstall skipifsilent unchecked
