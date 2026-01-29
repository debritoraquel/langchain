# Pipeline de extração para hifomicetos aquáticos

Este módulo automatiza a extração de descrições taxonômicas e imagens de PDFs, gerando
artefatos estruturados para uso em grafos de conhecimento (ex.: OpenSPG/Neo4j) e em
pipelines de visão computacional.

## Requisitos

```bash
python -m pip install pymupdf pillow
```

## Como executar no VS Code (Windows)

1. Abra o terminal integrado do VS Code no seu ambiente.
2. Instale as dependências no terminal (não no Run/Debug):

```powershell
python -m pip install pymupdf pillow
```

3. Execute o script apontando para a pasta de artigos e para um diretório de saída.

> **Importante (PowerShell):** não use `\` para quebrar linha. Use uma linha única ou o
> acento grave `` ` `` para continuação.

```powershell
python cookbook/hifomicetos_extraction/extract_hifomicetos.py `
  --input-dir "D:/MBA/tcc/REFERENCIAS/CHAVES HIFOMICETOS" `
  --output-dir "D:/MBA/tcc/OUTPUT_HIFOMICETOS"
```

### Integração via Run and Debug

O repositório inclui uma configuração de depuração em `.vscode/launch.json` chamada
**Hifomicetos: Extrair PDFs**. Para usar:

1. Abra o painel **Run and Debug** no VS Code.
2. Selecione **Hifomicetos: Extrair PDFs**.
3. Ajuste os argumentos no `launch.json` se o caminho dos PDFs ou do diretório de saída
   for diferente.
4. Clique em **Run** (ou **F5**) para executar.

Se você vir erros do tipo `SyntaxError: invalid syntax` apontando para um arquivo chamado
`pip install ... .py`, significa que o comando de instalação foi executado pelo depurador
como se fosse um script. Execute a instalação apenas no terminal integrado (passo 2).

Se quiser priorizar espécies específicas (opcional):

```powershell
python cookbook/hifomicetos_extraction/extract_hifomicetos.py `
  --input-dir "D:/MBA/tcc/REFERENCIAS/CHAVES HIFOMICETOS" `
  --output-dir "D:/MBA/tcc/OUTPUT_HIFOMICETOS" `
  --species "Lunulospora curvula" "Triscelophorus monosporus"
```

## Saídas geradas

- `taxonomic_descriptions.json`: descrições taxonômicas estruturadas.
- `image_annotations.json`: metadados de imagens, categorias morfológicas e anotações.
- `figures/`: diretório com figuras extraídas e metadados por PDF.

## Integração com grafo de conhecimento

Os JSONs gerados podem ser ingeridos em pipelines do LangChain + OpenSPG para construir
entidades e relações (espécies, caracteres morfológicos, habitats, referências, etc.).
