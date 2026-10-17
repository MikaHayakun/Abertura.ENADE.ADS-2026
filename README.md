# Abertura ENADE.ADS–2026

[**Assistir à abertura e jogar →**](https://enade-ads-2026-abertura.vercel.app)

Abertura 3D do projeto ENADE.ADS–2026, um jogo educativo independente para estudar Análise e Desenvolvimento de Sistemas. O vídeo tem 15,2 segundos, em Full HD horizontal, e termina com uma chamada interativa para entrar no jogo.

Este repositório público contém o player, o vídeo aprovado e o código da animação. Você pode fazer fork, estudar o código, propor melhorias e enviar pull requests. O código do jogo é mantido separadamente, em um repositório privado.

## Assistir e compartilhar

Use **https://enade-ads-2026-abertura.vercel.app** em páginas, botões e materiais de divulgação. Esse é o endereço de entrada do projeto.

Depois da última frase, o botão **Jogar agora** aparece aos 13 segundos, com letras em blocos e iluminação verde. Ele permanece após o vídeo terminar e abre o jogo. O endereço técnico do jogo é usado somente como destino desse botão para evitar que o público pule a apresentação.

## Rodar localmente

Requer apenas Python 3 para assistir ao vídeo pronto:

```bash
git clone https://github.com/MikaHayakun/Abertura.ENADE.ADS-2026.git
cd Abertura.ENADE.ADS-2026
python3 scripts/serve.py
```

Abra **http://localhost:4173**. A apresentação aparece limpa, sem barra de tempo, cronômetro ou botões de controle sobre o vídeo. Clique na imagem para entrar em tela cheia; no celular, basta um toque nos navegadores compatíveis. Em tela cheia, clique/toque ou pressione **Espaço** para pausar/continuar. **F** alterna a tela cheia e **R** permite assistir novamente. Um clique duplo dentro da tela cheia permite sair. A chamada final permanece visível em tela cheia. Com movimento reduzido, a reprodução aguarda um clique ou a tecla Espaço.

## No celular

Em telas de celular, a página seleciona automaticamente o vídeo **vertical, 720 × 1280, com uma única formação**. Em pé, ele preenche a janela; ao girar o aparelho, o vídeo vertical é preservado sem cortar a cena. As três frases, seus tempos e a chamada Jogar agora aos 13 s são mantidos. No mobile, o feixe de iluminação fica contido no botão; a iluminação do computador permanece igual. O player continua limpo, sem controles sobrepostos.

No computador, o vídeo horizontal aprovado, com as duas formações, permanece sem alterações.

Para gerar somente a versão mobile:

```bash
python3 scripts/render_opening.py --format portrait --copies 1
```

## Como a animação funciona

As capturas são referências para construir geometria tridimensional. Elas não aparecem como fotos ou painéis dentro da cena.

- À esquerda: portal → cinco distritos → prédio.
- À direita: cinco distritos → portal → prédio, com entrada, ordem de encaixe e giro diferentes.
- As duas formações se montam simultaneamente e terminam com os prédios completos juntos, por volta de 12,8 segundos.
- O fundo, a montagem e as frases avançam de forma independente.
- As frases usam letras 3D arredondadas em Nunito; apenas a chamada final usa letras feitas de cubos. A saída das frases limpa letras, sombras e partículas juntas, sem deixar contornos apagados entre as mensagens.

| Tempo | Conteúdo |
| --- | --- |
| 0,25–5,35 s | Um jogo educativo independente para estudar Análise e Desenvolvimento de Sistemas |
| 5,5–8,93 s | Acerte os desafios por fases |
| 9,1–12,8 s | Reconstrua uma cidade digital enquanto constrói aprendizado real |
| 6–12,8 s | Montagem final dos dois prédios |
| A partir de 13 s | Jogar agora; a chamada permanece após o fim |

## Arquivos principais

| Caminho | Função |
| --- | --- |
| `index.html` | Player e botão interativo final |
| `output/ENADE.ADS-2026-abertura-3D-dupla-dinamica.mp4` | Vídeo aprovado, 1920 × 1080, H.264, 25 fps, sem áudio |
| `output/dupla-dinamica.vtt` | Legendas opcionais |
| `output/dupla-dinamica.json` | Tempos e sequência das duas formações |
| `scripts/render_opening.py` | Cena OpenGL/EGL e exportação do vídeo |
| `scripts/scene_geometry.py` | Modelos do portal, das torres e do prédio |
| `scripts/block_phrases.py` | Frases e geometria das letras |
| `scripts/serve.py` | Servidor local, com suporte à busca no vídeo |
| `assets/` | Fontes e suas licenças |

## Renderizar uma nova versão

A reprodução do vídeo pronto não precisa destas dependências. Para editar e renderizar a cena, use Python 3.11 ou superior, FFmpeg e uma implementação Mesa/OpenGL com EGL. As versões de bibliotecas usadas estão em `requirements-render.txt`.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-render.txt
python3 scripts/render_opening.py --format landscape --copies 2 --stills
python3 scripts/render_opening.py --format landscape --copies 2
```

Os arquivos saem em `output/`. O renderer usa um núcleo, prioridade baixa e cache dos quadros de fundo em disco para reduzir a carga no computador. Não rode renderização e navegador de conferência ao mesmo tempo em máquinas com pouca memória.

As capturas e o vídeo de referência estão na raiz para permitir a reprodução da cena. As fachadas da captura final são retificadas e aplicadas ao próprio prédio 3D. As fontes Nunito e Fira estão incluídas, com suas licenças.

## Publicar

O player é um site estático, sem servidor de aplicação. Na Vercel, use o preset **Other**, sem comando de build, e a raiz do repositório como diretório de saída. O arquivo `vercel.json` contém essas opções. Verifique a reprodução e o botão final no endereço publicado antes de trocar links de divulgação.

## Contribuir

Leia [CONTRIBUTING.md](CONTRIBUTING.md). Use as [issues](https://github.com/MikaHayakun/Abertura.ENADE.ADS-2026/issues) para sugestões e problemas da abertura e envie pull requests para alterações de código. Os templates ajudam a indicar o instante do vídeo e o comportamento esperado.

O código original está sob a [licença MIT](LICENSE). Fontes e materiais de referência têm os termos descritos em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
