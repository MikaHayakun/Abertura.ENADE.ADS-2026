# Como contribuir

Sugestões, correções e novas ideias para a abertura são bem-vindas.

## Sugerir ou relatar um problema

Abra uma issue e informe o que gostaria de mudar. Para problemas visuais, indique o instante do vídeo, o navegador, o tamanho da janela e se estava em tela cheia. Inclua uma captura quando ela ajudar a mostrar o problema.

## Enviar código

1. Faça um fork e crie uma branch para sua alteração.
2. Rode `python3 scripts/serve.py` e confira em `http://localhost:4173`.
3. Altere apenas os arquivos relacionados à proposta e faça commits com mensagens claras.
4. Abra um pull request explicando o problema, a mudança e a verificação feita.

Para mudanças no vídeo, envie capturas antes/depois e os tempos afetados. Não é preciso renderizar tudo para uma proposta inicial: os quadros gerados com `--stills` ajudam a revisar a composição.

## Comportamentos a preservar

- Usar geometria 3D e duas montagens simultâneas diferentes.
- Manter o fundo em movimento, independente das frases.
- Manter letras arredondadas e legíveis nas três frases.
- Concluir os prédios perto de 12,8 s e apresentar Jogar agora aos 13 s.
- Preservar o botão em tela cheia, após o vídeo terminar e ao sair da tela cheia.
- Ocultar a chamada ao reiniciar ou voltar para antes de 13 s.
- Respeitar preferência por movimento reduzido.
- Usar o endereço da abertura em toda divulgação. Apenas o botão final direciona ao jogo.

## Arquivos e materiais

Não envie caches de renderização, ambientes Python, credenciais de hospedagem ou arquivos `.vercel/`. Preserve os avisos e licenças das fontes. Para novos materiais visuais, informe a autoria e os termos de uso no pull request.

O código privado do jogo não faz parte deste repositório. Sugestões sobre a experiência da abertura podem ser discutidas aqui sem compartilhar esse código.
