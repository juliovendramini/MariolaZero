@echo off
rem Refaz casas\casa_julio.json a partir da planta em DXF (ILUMINACAO E GESSO, dez/2020).
rem Os nomes dos blocos sao os do desenho; "z" = cozinha e "al" = area de lazer sao palpites a conferir.
cd /d "%~dp0.."
python ferramentas\planta_dxf.py "%USERPROFILE%\Documents\modelos3D\robotica\roboCasa\planta\planta_iluminacao_gesso.dxf" casas\casa_julio.json --nome "casa do Julio" --moveis-dos-blocos --nomes "gar=Garagem,sala=Sala de estar,s jantar=Sala de jantar,z=Cozinha,q 01=Quarto 1,QUARTO 2=Quarto 2,Q CASAL=Quarto casal,CLOSET=Closet,b social=Banheiro social,b. casal=Banheiro casal,ASER=Area de servico,lavaaaaa=Lavanderia,al=Area de lazer,dec=Deck,pis=Piscina" %*
