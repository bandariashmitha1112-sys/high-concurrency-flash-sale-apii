import { useEffect, useState } from "react"
const API_URL = import.meta.env.VITE_API_URL

console.log("API URL:", API_URL)

function App() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loggedIn, setLoggedIn] = useState(
    !!localStorage.getItem("access_token")
  )

  const [products, setProducts] = useState([])
  const [message, setMessage] = useState("")
  const [quantities, setQuantities] = useState({})

  const handleLogin = async (event) => {
    event.preventDefault()

    const formData = new URLSearchParams()
    formData.append("username", username)
    formData.append("password", password)

    try {
      const response = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
      })

      const data = await response.json()
      console.log("Login response:", response.status, data)
      if (!response.ok) {
        setMessage(data.detail || "Login failed")
        return
      }

      localStorage.setItem("access_token", data.access_token)

      setLoggedIn(true)
      setMessage("")
    } catch (error) {
      setMessage("Could not connect to backend")
    }
  }

  const loadProducts = async () => {
    const token = localStorage.getItem("access_token")

    try {
      const response = await fetch(`${API_URL}/products`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })

      const data = await response.json()

      if (!response.ok) {
        setMessage(data.detail || "Failed to load products")
        return
      }

      setProducts(data)
    } catch (error) {
      setMessage("Could not connect to backend")
    }
  }
  const handlePurchase = async (productId, quantity) => {
  const token = localStorage.getItem("access_token")
  console.log("Purchase token exists:", !!token)
  const idempotencyKey = crypto.randomUUID()
  console.log("BUY CLICKED → productId:", productId, "quantity:", quantity)

  try {
    const response = await fetch(
      `${API_URL}/products/${productId}/purchase`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          quantity: quantity,
        }),
      }
    )

    const data = await response.json()

    console.log(
      "Purchase response:",
      response.status,
      data.detail || data
    )

    if (!response.ok) {
      setMessage(data.detail || "Purchase failed")
      return
    }

    setMessage(`Order successful! Order ID: ${data.order_id}`)

    await loadProducts()
  } catch (error) {
    console.error("Purchase error:", error)
    setMessage("Could not connect to backend")
  }
}

  useEffect(() => {
    if (loggedIn) {
      loadProducts()
    }
  }, [loggedIn])

  // LOGIN PAGE
  if (!loggedIn) {
    return (
      <div>
        <header>
          <h1>⚡ Flash Sale</h1>
          <p>High-Concurrency Shopping System</p>
        </header>

        <main>
          <h2>Login</h2>

          <form onSubmit={handleLogin}>
            <div>
              <label>Username</label>
              <br />
              <input
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Enter username"
              />
            </div>

            <br />

            <div>
              <label>Password</label>
              <br />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
              />
            </div>

            <br />

            <button type="submit">
              LOGIN
            </button>
          </form>

          <p>{message}</p>
        </main>
      </div>
    )
  }

  // PRODUCTS PAGE
  return (
    <div>
      <header>
        <h1>⚡ Flash Sale</h1>
        <p>High-Concurrency Shopping System</p>
      </header>

      <main>
        <h2>🔥 Flash Sale Products</h2>

        {message && <p>{message}</p>}

        {products.map((product) => (
          <div key={product.id}>
  <h3>{product.name}</h3>

  <p>Price: ₹{product.price}</p>
  <p>Stock: {product.stock}</p>

  <label>Quantity: </label>

  <input
    type="number"
    min="1"
    max={Math.min(product.stock, 10)}
    value={quantities[product.id] || 1}
    onChange={(event) => {
      const value = Math.max(
        1,
        Math.min(
          Number(event.target.value),
          Math.min(product.stock, 10)
        )
      )

      setQuantities({
        ...quantities,
        [product.id]: value,
      })
    }}
  />

  <p>
    Total: ₹{product.price * (quantities[product.id] || 1)}
  </p>

  <button
    onClick={() =>
      handlePurchase(
        product.id,
        quantities[product.id] || 1
      )
    }
    disabled={product.stock === 0}
  >
    {product.stock === 0 ? "SOLD OUT" : "BUY NOW"}
  </button>
</div>
        ))}
      </main>
    </div>
  )
}

export default App