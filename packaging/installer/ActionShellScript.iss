; ActionShellScript installer draft
; Install source: release_stage\dist

#ifndef ReleaseSourceRoot
#define ReleaseSourceRoot "..\..\release_stage"
#endif
#ifndef InstallerOutputRoot
#define InstallerOutputRoot "..\..\release_stage\installer"
#endif

#define MyAppName "ActionShellScript"
#ifndef MyAppVersion
#define MyAppVersion "0.2.0a2"
#endif
#ifndef MyAppFileVersion
#define MyAppFileVersion "0.2.0.1"
#endif
#define MyAppPublisher "ActionShellScript"
#define MyAppURL "https://github.com/CoderDawg/ActionShellScript"
#define MyAppExeName "ass-gui.exe"
[Setup]
AppId={{A4C5C8DE-8F9B-4B2A-AF7C-9E6F7A1C2B10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
OutputDir="{#InstallerOutputRoot}"
OutputBaseFilename={#MyAppName}-Setup
SetupIconFile={#InstallerSetupIcon}
UninstallDisplayIcon={app}\ass-gui\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
VersionInfoVersion={#MyAppFileVersion}
VersionInfoDescription={#MyAppName} installer
VersionInfoCompany={#MyAppPublisher}
LicenseFile={#ReleaseSourceRoot}\ATTRIBUTION.txt

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#ReleaseSourceRoot}\dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[UninstallDelete]
; Remove the installed application tree and the app-owned per-user data tree
; so the standard uninstall path leaves no ActionShellScript leftovers behind.
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{userappdata}\ActionShellScript"

[Icons]
Name: "{group}\ActionShellScript GUI"; Filename: "{app}\ass-gui\ass-gui.exe"; WorkingDir: "{app}\ass-gui"
Name: "{group}\ActionShellScript Help"; Filename: "{app}\ass-help\ass-help.exe"; WorkingDir: "{app}\ass-help"
Name: "{group}\ActionShellScript CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\ass-cli\ass-cli.exe"" --help"; WorkingDir: "{app}\ass-cli"; IconFilename: "{app}\ass-cli\ass-cli.exe"

[Run]
Filename: "{app}\ass-gui\ass-gui.exe"; Description: "Launch ActionShellScript GUI"; Flags: nowait postinstall skipifsilent
