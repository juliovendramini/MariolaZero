# `Cronometro` — medir tempo (e lembrar dele depois de reiniciar)

Arquivo: `libs/cronometro.py` · `from cronometro import Cronometro`

## Para que serve

Medir quanto tempo passou, em **milissegundos**, de um jeito legível:

* "fiquei 5 s parado no azul?", "faz quanto tempo que perdi a linha?";
* limitar o tempo de uma manobra (girar no máximo 3 s);
* saber quanto falta da rodada de 8 minutos — **mesmo depois de o programa reiniciar** num LoP,
  se o cronômetro tiver um arquivo.

## Métodos

### `Cronometro(nome_arquivo=None)`
Sem arquivo: cronômetro comum. Com arquivo: cada `inicia()`/`reseta()` grava o instante de início
nele, e `carrega()` recupera.

### `inicia()` · `reseta()`
Começa a contar a partir de agora (e grava, se tiver arquivo). Os dois fazem o mesmo.

### `tempo()` → ms desde o início (ou `None` se nunca iniciou)

### `carrega()`
Lê o início do arquivo. Se o arquivo não existe ou está estragado, **inicia agora** e grava.

### `salva()` · `apaga()`
Grava o início no arquivo / apaga o arquivo (`rm`).

## Receitas

**Tempo máximo de uma manobra:**
```python
c = Cronometro()
c.inicia()
while c.tempo() < 3000 and not achou_linha():
    ...
```

**Relógio da rodada que sobrevive a um reinício:**
```python
rodada = Cronometro('/home/banana/rodada.txt')
if comecando_rodada_nova:          # ex.: escolhido no menu, ou o arquivo é de outra rodada
    rodada.inicia()
else:
    rodada.carrega()               # LoP: o programa reiniciou, o tempo continua
if rodada.tempo() > 6.5 * 60 * 1000:
    print('hora de voltar para o início')
```

* **Cuidado:** o tempo vem do relógio do Linux (`time.time()`). Se o relógio do brick mudar no meio
  (sincronizou pela internet), a conta pula. Num arquivo de checkpoint, guarde também o instante e
  confira se ele faz sentido (o exemplo da Maze descarta checkpoint com mais de 8 minutos).
* Com a partição principal somente leitura, grave os arquivos na sua pasta em `/home/banana/`.

## No simulador

`time.time()` segue o relógio simulado, então o `Cronometro` também (pausa, 4x, etc.).
