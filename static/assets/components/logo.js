const logoStyle = `
<style>

  .logo{
    display:flex;
    align-items:center;
    gap:30px;
  }

  .adidas-logo{
    width:48px;
    height:30px;
  }

  .supernova-logo{
    width:164px;
  }
</style>
`;

const logo = ` 
  <div class="logo">
    <img src="../../static/assets/images/logos/adidas.png" alt="logo-adidas" class="adidas-logo"/>
  </div>
`;

class Logo extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = logoStyle + logo;
  }
}
customElements.define("logo-component", Logo);
