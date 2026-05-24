// role_manager.js - Gestión de roles y permisos

let currentUser = {
    username: '',
    role: '',
    name: ''
};

async function carregarUserRole() {
    try {
        const response = await fetch('/api/user-role');
        const data = await response.json();
        currentUser = data;
        aplicarPermissoes();
        return data;
    } catch (error) {
        console.error('Erro ao carregar papel do usuário:', error);
        return null;
    }
}

function aplicarPermissoes() {
    const role = currentUser.role;
    const navTabs = document.querySelectorAll('.nav-tab');
    
    navTabs.forEach(tab => {
        const href = tab.getAttribute('href');
        
        if (href === '/configuracoes') {
            if (role !== 'admin') {
                tab.style.opacity = '0.5';
                tab.style.pointerEvents = 'none';
                tab.style.cursor = 'not-allowed';
                tab.title = 'Apenas administradores';
            }
        }
        else if (href === '/' || href === '/incidencias/ativas' || href === '/incidencias/fechadas' || href === '/relatorios') {
            if (role === 'operador') {
                tab.style.opacity = '0.5';
                tab.style.pointerEvents = 'none';
                tab.style.cursor = 'not-allowed';
                tab.title = 'Apenas técnicos e administradores';
            }
        }
    });
    
    if (role === 'operador') {
        const botoesEditar = document.querySelectorAll('.btn-outline');
        botoesEditar.forEach(btn => {
            if (btn.textContent.includes('Editar') || btn.textContent.includes('Ver')) {
                btn.style.display = 'none';
            }
        });
        const botoesFechar = document.querySelectorAll('.btn-danger');
        botoesFechar.forEach(btn => {
            if (btn.textContent.includes('Fechar')) {
                btn.style.display = 'none';
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    carregarUserRole();
    if (typeof inicializarAutoPreenchimento === 'function') {
        inicializarAutoPreenchimento();
    }
});