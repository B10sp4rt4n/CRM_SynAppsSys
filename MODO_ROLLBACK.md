# 🔓 Modo Rollback - Guía de Uso

## 📋 ¿Qué es el Modo Rollback?

El **Modo Rollback** es una configuración de seguridad que permite desarrollar y probar el CRM sin los requisitos completos de autenticación AUP, evitando errores de trazabilidad y registro de eventos mientras se trabaja en mejoras visuales o funcionales.

## 🎯 Estado Actual

- **Modo:** `AUTH_ROLLBACK_MODE = True`
- **Versión:** `1.3.ROLLBACK`
- **Características desactivadas:**
  - ✅ Registro de eventos en `aup_eventos`
  - ✅ Registro de historial en `aup_historial`
  - ✅ Validaciones estrictas de usuario

## 🔧 Configuración

El modo se controla desde `core/config_global.py`:

```python
AUTH_ROLLBACK_MODE = True  # Modo desarrollo seguro
```

## 📊 Indicador Visual

En la sidebar verás:

```
🧭 Estado del Sistema
Modo autenticación: 🔓 Rollback
Versión: 1.3.ROLLBACK
Entorno: development
```

## 🔄 Cómo Reactivar Modo Completo

Cuando termines las pruebas y quieras volver a la arquitectura AUP completa:

1. Edita `core/config_global.py`:
```python
AUTH_ROLLBACK_MODE = False
APP_VERSION = "1.4.AUP-AUTH"
```

2. Reinicia la aplicación

3. Verifica que aparezca: `Modo autenticación: 🔐 Estructurado`

## ✅ Beneficios

| Función | Resultado |
|---------|-----------|
| 🧩 Control centralizado | Todos los módulos saben el estado del sistema |
| 🧠 Autoprotección | Evita errores de usuarios inexistentes |
| 🧮 Versionado explícito | Marca clara del estado (ROLLBACK) |
| 🧰 Desarrollo sin fricción | Permite trabajar en UI/Dashboard sin bloqueos |
| 🔄 Reversible | Un switch para reactivar todo |

## 📝 Módulos Afectados

- `core/event_logger.py` - No registra eventos
- `core/config_global.py` - Configuración central
- `ui/main_app.py` - Muestra estado en sidebar

## ⚠️ Importante

Este modo es **SOLO para desarrollo**. En producción debe estar en `False` para mantener trazabilidad completa.
