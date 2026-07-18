import streamlit as st
import spacy
from spacy import displacy
from docx import Document
from pypdf import PdfReader

# Configuração da página do Streamlit
st.set_page_config(page_title="Extração de Entidades Pro", page_icon="🔍", layout="centered")

st.title("🔍 Extração Inteligente de Pessoas e Empresas (NER)")
st.write("Faça o upload do documento (.txt, .docx ou .pdf). Esta versão combina IA com regras precisas de escopo.")

@st.cache_resource
def load_nlp():
    try:
        nlp = spacy.load("pt_core_news_sm")
    except IOError:
        nlp = spacy.load("en_core_web_sm")
        
    if "entity_ruler" not in nlp.pipe_names:
        # Adiciona o ruler ANTES do NER e força a sobrescrita de entidades conflitantes
        ruler = nlp.add_pipe("entity_ruler", before="ner", config={"overwrite_ents": True})
        
        # Padrões corrigidos para evitar comportamento guloso e capturar apenas as palavras-alvo
        patterns = [
            # 1. REGRA ULTRA PRECISA PARA PESSOAS (Garante gatilhos + conectores opcionais + Nome)
            {
                "label": "PER_SUGGESTED", 
                "pattern": [
                    # Identifica o cargo/gatilho
                    {"LOWER": {"IN": ["chamado", "chamada", "nome", "senhor", "sr", "dr", "funcionario", "funcionaria", "colaborador", "colaboradora"]}}, 
                    # Ignora conectores opcionais como "que", "se", "chama", "o", "a"
                    {"LOWER": {"IN": ["que", "se", "chama", "o", "a", "por"]}, "OP": "?"},
                    {"LOWER": {"IN": ["que", "se", "chama", "o", "a", "por"]}, "OP": "?"},
                    # Captura estritamente o nome (uma ou duas palavras)
                    {"IS_ALPHA": True, "OP": "+"}
                ]
            },
            
            # 2. REGRA ULTRA PRECISA PARA EMPRESAS (Garante gatilho + conectores opcionais + Nome da Empresa)
            {
                "label": "ORG", 
                "pattern": [
                    {"LOWER": {"IN": ["empresa", "laticínios", "indústria", "fábrica", "loja", "grupo", "banco", "agência", "escritório"]}},
                    {"LOWER": {"IN": ["de", "da", "do", "dos", "das", "e", "chamada", "chamado"]}, "OP": "?"},
                    {"IS_ALPHA": True, "OP": "+"}
                ]
            },
            
            # Redes de segurança padrão para nomes próprios com maiúsculas isoladas
            {"label": "PER_SUGGESTED", "pattern": [{"IS_TITLE": True}, {"IS_TITLE": True}]},
            {"label": "PER_SUGGESTED", "pattern": [{"IS_TITLE": True}, {"IS_TITLE": True}, {"IS_TITLE": True}]}
        ]
        ruler.add_patterns(patterns)
        
    return nlp

# Inicializa o modelo global do spaCy
nlp = load_nlp()

# Função auxiliar para ler diferentes formatos de arquivos com tratamento de caracteres ocultos
def extract_text_from_file(file):
    file_name = file.name.lower()
    text = ""
    
    if file_name.endswith('.txt'):
        text = file.read().decode("utf-8")
        
    elif file_name.endswith('.docx'):
        doc_word = Document(file)
        full_text = [paragraph.text for paragraph in doc_word.paragraphs]
        text = '\n'.join(full_text)
        
    elif file_name.endswith('.pdf'):
        pdf_reader = PdfReader(file)
        full_text = []
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                full_text.append(page_text)
        text = '\n'.join(full_text)
        
    # Correção de erro: Remove espaços sem quebra (\xa0) comuns em arquivos convertidos
    return text.replace("\xa0", " ")

# Área de Upload do Documento
uploaded_file = st.file_uploader("Escolha um arquivo para analisar", type=["txt", "docx", "pdf"])

if uploaded_file is not None:
    with st.spinner("Lendo conteúdo do arquivo..."):
        text_content = extract_text_from_file(uploaded_file)
    
    with st.expander("Ver conteúdo original extraído"):
        st.write(text_content)
    
    if st.button("Iniciar Extração de Entidades", type="primary"):
        if text_content.strip() == "":
            st.warning("O arquivo enviado está vazio ou não possui texto legível.")
        else:
            with st.spinner("Processando texto com spaCy..."):
                doc = nlp(text_content)
                
                # Atualize essas duas linhas no seu laço de repetição principal:
                termos_limpar_org = ["empresa ", "laticínios ", "indústria ", "fábrica ", "loja ", "grupo ", "banco ", "agência ", "chamada ", "chamado "]
                termos_limpar_per = ["chamado ", "chamada ", "nome ", "senhor ", "sr ", "dr ", "funcionario ", "funcionaria ", "que se chama ", "que se chamava ", "o ", "a "]
                
                pessoas = []
                empresas = []
                
                for ent in doc.ents:
                    nome_limpo = ent.text
                    
                    # Processamento de Organizações
                    if ent.label_ == "ORG":
                        for termo in termos_limpar_org:
                            if nome_limpo.lower().startswith(termo):
                                nome_limpo = nome_limpo[len(termo):]
                        
                        nome_final = nome_limpo.strip()
                        # Validação para não inserir palavras vazias ou conectores soltos
                        if nome_final and len(nome_final) > 1 and nome_final not in empresas:
                            empresas.append(nome_final)
                            
                    # Processamento de Pessoas
                    elif ent.label_ in ["PER", "PERSON", "PER_SUGGESTED"]:
                        for termo in termos_limpar_per:
                            if nome_limpo.lower().startswith(termo):
                                nome_limpo = nome_limpo[len(termo):]
                        
                        # Formata strings (ex: eleno -> Eleno) e limpa espaços extras
                        nome_final = nome_limpo.strip().title()
                        if nome_final and len(nome_final) > 1 and nome_final not in pessoas:
                            pessoas.append(nome_final)
                
                st.markdown("---")
                st.subheader("Visualização Gráfica no Texto")
                
                # Renderização segura das marcações textuais
                options = {"ents": ["PER", "PERSON", "ORG", "PER_SUGGESTED"], "colors": {"PER_SUGGESTED": "#ffadad", "PER": "#ffadad", "PERSON": "#ffadad", "ORG": "#8ecae6"}}
                html_vis = displacy.render(doc, style="ent", options=options, page=False)
                st.write(html_vis, unsafe_allow_html=True)
                
                st.markdown("---")
                st.subheader("📌 Lista de Entidades Extraídas")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### 👤 Pessoas")
                    if pessoas:
                        for p in sorted(pessoas):
                            st.write(f"- {p}")
                    else:
                        st.info("Nenhum nome de pessoa encontrado.")
                        
                with col2:
                    st.markdown("### 🏢 Empresas / Organizações")
                    if empresas:
                        for e in sorted(empresas):
                            st.write(f"- {e}")
                    else:
                        st.info("Nenhuma empresa encontrada.")