; Windows kurulum dosyası (Inno Setup 6)
; Derleme: iscc /DAppVersion=1.0.0 packaging\windows\installer.iss
; Önce: pyinstaller packaging/mp3donusturucum.spec --noconfirm

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6F1C2B7E-3D4A-4E8B-9C21-5A7D8E9F0B13}
AppName=MP3 Dönüştürücüm
AppVersion={#AppVersion}
AppPublisher=efebalci569-dot
AppPublisherURL=https://github.com/efebalci569-dot/mp3-donusturucu
DefaultDirName={localappdata}\Programs\MP3Donusturucum
DefaultGroupName=MP3 Dönüştürücüm
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=MP3Donusturucum-Windows-Kurulum
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=MP3 Dönüştürücüm
UninstallDisplayIcon={app}\MP3Donusturucum.exe
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\MP3Donusturucum\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MP3 Dönüştürücüm"; Filename: "{app}\MP3Donusturucum.exe"
Name: "{autodesktop}\MP3 Dönüştürücüm"; Filename: "{app}\MP3Donusturucum.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MP3Donusturucum.exe"; Description: "{cm:LaunchProgram,MP3 Dönüştürücüm}"; Flags: nowait postinstall skipifsilent
