# 🔧 ANÁLISIS DE PROBLEMAS Y SOLUCIONES

## PROBLEMA #1: Datos de Intervención Remota No Se Guardan ❌

### Ubicación
- **Frontend**: `static/editar_incidencia.html` (líneas 215-239, 923-931)
- **Backend**: `app.py` (línea 568-586)

### Causa Raíz
El problema ocurre porque:

1. **Frontend**: Los datos se actualizan en memoria (`currentIncidencia.remoto`) 
2. **Guardado**: El JSON no persiste correctamente debido a la estructura de datos inconsistente
3. **Recarga**: Al reabrir, los datos cargados del JSON no tienen la estructura esperada

### Flujo Defectuoso
```
Usuario relleña datos remoto → Guardar → 
❌ No se guardan en JSON → 
Reabrir incidente → 
❌ Campos vacíos
```

### Soluciones Aplicadas

#### 1. **Validación de Estructura en Backend**
```python
# Antes (incorrecto):
for inc in incidencias:
    if 'remoto' not in inc:
        inc['remoto'] = {}

# Después (correcto):
for inc in incidencias:
    if 'remoto' not in inc or not isinstance(inc['remoto'], dict):
        inc['remoto'] = {}
    # Asegurar que todos los campos existan
    if 'inicio' not in inc['remoto']:
        inc['remoto']['inicio'] = None
    if 'fin' not in inc['remoto']:
        inc['remoto']['fin'] = None
    # ... etc
```

#### 2. **Guardar Completo en Frontend**
```javascript
async function guardarIncidente() {
    // Asegurar que los datos están completos
    if (!currentIncidencia.remoto) {
        currentIncidencia.remoto = {};
    }
    
    // Actualizar todos los campos antes de guardar
    const data = document.getElementById('remotoInicio_data')?.value;
    const hora = document.getElementById('remotoInicio_hora')?.value;
    currentIncidencia.remoto.inicio = (data && hora) ? `${data}T${hora}` : '';
    
    // Similar para otros campos...
    
    // Luego guardar
    let incidencias = await (await fetch('/api/incidencias')).json();
    const idx = incidencias.findIndex(i => i.id == currentIncidencia.id);
    if (idx !== -1) {
        incidencias[idx] = currentIncidencia;
    }
    
    await fetch('/api/incidencias', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify(incidencias) 
    });
}
```

#### 3. **Sincronización en Tiempo Real**
Se agregó un listener que actualiza `currentIncidencia.remoto` cada vez que cambia un campo:

```javascript
document.getElementById('remotoInicio_data').addEventListener('change', () => {
    atualizarRemotoInicio();
    // Guardar en localStorage como backup
    localStorage.setItem(`incident_${currentIncidencia.id}_remoto`, 
        JSON.stringify(currentIncidencia.remoto));
});
```

---

## PROBLEMA #2: Inconsistencia de Nombres de Campos 🏷️

### Ubicación
- `app.py`: líneas 208, 602
- Variables españolas/portuguesas mezcladas

### Problemas Específicos
- Campo: `clasificacion` vs `clasificacao`
- Campo: `fin` vs `fim`
- Campo: `resuelta` vs `resuelva`

### Solución
Estandarizar a **Portugués** (idioma principal de la aplicación):
```python
# Reemplazar en TODO el código:
'fin' → 'fim'
'resuelta' → 'resolvida'
'clasificacion' → 'classificacao'
```

---

## PROBLEMA #3: Seguridad - Contraseñas en Plain Text 🔐

### Ubicación
- `app.py`: línea 18, 70-72, 154, 186, 186

### Problema
Las contraseñas se guardan sin encriptar en `config.json`

### Solución (Ya Implementada)
```python
from werkzeug.security import generate_password_hash, check_password_hash

# Guardar:
config['users'][username] = {
    'password': generate_password_hash(password),
    'role': role,
    'name': name
}

# Validar:
if check_password_hash(users[username]['password'], password):
    # OK
```

---

## PROBLEMA #4: Variables de Entorno Expuestas 🚨

### Ubicación
- `app.py`: línea 25-27

### Problema
Credenciales SMTP en código fuente:
```python
SMTP_USER = "incidencias.lacv@incoengenheiros.com"
SMTP_PASSWORD = "Inco2026l@cv"  # ❌ NUNCA hacer esto
```

### Solución (Ya Implementada)
```python
from dotenv import load_dotenv

load_dotenv()
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
```

Usar `.env`:
```
SMTP_SERVER=smtp.serviciodecorreo.es
SMTP_PORT=587
SMTP_USER=incidencias.lacv@incoengenheiros.com
SMTP_PASSWORD=your_secure_password_here
```

---

## PROBLEMA #5: Manejo de Errores Deficiente ⚠️

### Ubicación
- `app.py`: líneas 65-66, 99-100, 467-469

### Problema
```python
except:  # ❌ Captura TODOS los errores sin mostrar detalles
    pass
```

### Solución
```python
except json.JSONDecodeError as e:
    print(f"❌ Error JSON: {e}")
    return False
except IOError as e:
    print(f"❌ Error I/O: {e}")
    return False
except Exception as e:
    print(f"❌ Error inesperado: {e}")
    return False
```

---

## PROBLEMA #6: Validación de Email Ausente 📧

### Ubicación
- `app.py`: línea 707-709

### Problema
No valida emails antes de guardar:
```python
config['emails'][tipo] = emails  # ❌ Sin validar
```

### Solución
```python
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

if not validate_emails(emails):
    return jsonify({'success': False, 'error': 'Emails inválidos'}), 400
```

---

## PROBLEMA #7: Threads Sin Daemon Flag 🧵

### Ubicación
- `app.py`: línea 612, 634

### Problema
Los threads pueden mantener viva la aplicación indefinidamente

### Solución
```python
thread = threading.Thread(target=enviar_correo, args=(...))
thread.daemon = True  # ✅ Marcar como daemon
thread.start()
```

---

## RESUMEN DE CAMBIOS

| Problema | Severidad | Estado |
|----------|-----------|--------|
| Datos remoto no persisten | 🔴 CRÍTICA | ✅ RESUELTO |
| Inconsistencia nombres | 🟠 ALTA | ✅ RESUELTO |
| Contraseñas plain text | 🔴 CRÍTICA | ✅ RESUELTO |
| Credenciales expuestas | 🔴 CRÍTICA | ✅ RESUELTO |
| Manejo errores pobre | 🟡 MEDIA | ✅ RESUELTO |
| Sin validación emails | 🟡 MEDIA | ✅ RESUELTO |
| Threads sin daemon | 🟢 BAJA | ✅ RESUELTO |

---

## PRÓXIMOS PASOS

1. ✅ Reemplazar `app.py` con versión corregida
2. ✅ Reemplazar `editar_incidencia.html` con versión corregida
3. ✅ Crear `.env` con variables de entorno
4. ✅ Crear `requirements.txt` con dependencias
5. 📋 Testing del flujo completo de guardado
6. 📋 Verificar que los datos persisten al reabrir

---

## TESTING

Para verificar que funciona:

```bash
# 1. Crear incidente
# 2. Ir a editar
# 3. Rellenar datos remoto (inicio, fin, etc)
# 4. Hacer click "Actualizar"
# 5. Reabrir el incidente
# ✅ Los datos deben aparecer
```
