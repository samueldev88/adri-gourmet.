# Adriê Gourmet — loja online em Django

Sistema completo de loja online: catálogo de produtos com desconto,
carrinho, checkout com verificação de raio de entrega por CEP,
pagamento via Mercado Pago e controle de estoque com histórico de
movimentações.

## Arquitetura (visão geral)

```
catalog/    -> Categoria, Produto, Desconto (o que é vendido)
inventory/  -> Movimentação de estoque (auditoria: toda entrada/saída fica registrada)
cart/       -> Carrinho de compras (guardado na sessão do visitante)
delivery/   -> Cálculo de distância a partir do CEP + "recados" de fora da área
orders/     -> Pedido e Itens do pedido (o que foi comprado, snapshot do preço)
payments/   -> Integração com o Mercado Pago (Checkout Pro) + webhook de confirmação
```

Por que separado assim? Cada app cuida de uma responsabilidade só. Isso
facilita manutenção (ex: trocar o Mercado Pago por outro gateway no futuro
significa mexer só em `payments/`, sem tocar no resto).

## Decisões importantes (e por quê)

1. **Estoque nunca é editado diretamente.** Toda mudança de quantidade
   (venda, reposição, ajuste manual) passa pela função `adjust_stock()`
   em `inventory/services.py`, que cria um registro de auditoria. Assim
   dá pra responder "por que esse produto ficou sem estoque?" sempre.

2. **O preço de cada item do pedido é "congelado" no momento da compra**
   (`OrderItem.unit_price`). Se um desconto expirar ou o preço do produto
   mudar depois, o pedido já feito não muda de valor.

3. **A confirmação de pagamento vem do webhook do Mercado Pago, nunca da
   tela de retorno do navegador.** A pessoa pode fechar o navegador, ter
   quedado de internet etc. — só o webhook é fonte confiável de que o
   dinheiro realmente caiu.

4. **O cálculo de distância usa o CEP em duas etapas, sem custo:**
   ViaCEP (CEP → endereço) e depois Nominatim/OpenStreetMap
   (endereço → latitude/longitude), e por fim a fórmula de Haversine
   para medir a distância reta até a loja. Não precisa de cartão de
   crédito nem API paga do Google.

## Como rodar

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env com as credenciais do Mercado Pago e as coordenadas da loja

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse `/admin/` para cadastrar categorias, produtos e ver os pedidos —
é por ali que sua mãe vai gerenciar a loja no dia a dia, sem precisar
mexer em código.

## Descobrindo a latitude/longitude da loja

1. Abra o Google Maps e pesquise o endereço da loja.
2. Clique com o botão direito exatamente em cima do pino.
3. O primeiro item do menu mostra as coordenadas (ex: `-23.550520, -46.633308`).
4. Cole o primeiro número em `SHOP_LATITUDE` e o segundo em `SHOP_LONGITUDE`.

## O que falta para produção

- Trocar `MERCADOPAGO_ACCESS_TOKEN` de teste (`TEST-...`) pela credencial de produção.
- Configurar `SITE_URL` com o domínio real (o Mercado Pago precisa acessá-lo para o webhook).
- Trocar o banco SQLite por PostgreSQL se o volume de pedidos crescer.
- Configurar envio de e-mail ou notificação (ex: Telegram) para avisar
  a loja quando um pedido novo é pago — ponto de extensão já preparado
  em `payments/services.py`, função `notify_new_order()`.
