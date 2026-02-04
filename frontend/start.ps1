# Добавляем node_modules/.bin в PATH
$env:Path = "$PSScriptRoot\node_modules\.bin;$env:Path"
npm run dev
