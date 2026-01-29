# Pipeline de extração para hifomicetos aquáticos

Este módulo automatiza a extração de descrições taxonômicas e imagens de PDFs, gerando
artefatos estruturados para uso em grafos de conhecimento (ex.: OpenSPG/Neo4j) e em
pipelines de visão computacional.

## Requisitos

```bash
pip install pymupdf pillow
```

## Como executar no VS Code (Windows)

1. Abra o terminal integrado do VS Code no seu ambiente.
2. Execute o script apontando para a pasta de artigos e para um diretório de saída:

```bash
python cookbook/hifomicetos_extraction/extract_hifomicetos.py \
  --input-dir "D:/MBA/tcc/REFERENCIAS/CHAVES HIFOMICETOS" \
  --output-dir "D:/MBA/tcc/OUTPUT_HIFOMICETOS"
```

Se quiser priorizar espécies específicas (opcional):

```bash
python cookbook/hifomicetos_extraction/extract_hifomicetos.py \
  --input-dir "D:/MBA/tcc/REFERENCIAS/CHAVES HIFOMICETOS" \
  --output-dir "D:/MBA/tcc/OUTPUT_HIFOMICETOS" \
  --species "Lunulospora curvula" "Triscelophorus monosporus"
```

## Saídas geradas

- `taxonomic_descriptions.json`: descrições taxonômicas estruturadas.
- `image_annotations.json`: metadados de imagens, categorias morfológicas e anotações.
- `figures/`: diretório com figuras extraídas e metadados por PDF.

## Integração com grafo de conhecimento

Os JSONs gerados podem ser ingeridos em pipelines do LangChain + OpenSPG para construir
entidades e relações (espécies, caracteres morfológicos, habitats, referências, etc.).
