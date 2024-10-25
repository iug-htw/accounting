document.getElementById('menuButton').addEventListener('click', function() {
    var menu = document.getElementById('menu');
    if (menu.style.display === 'block') {
        menu.style.display = 'none';
    } else {
        menu.style.display = 'block';
    }
});

function showLoggedInView() {
    document.getElementById('loginContainer').style.display = 'none';
    document.querySelector('.navigation_bar_top').style.display = 'flex';
    document.getElementById('logoutContainer').style.display = 'flex'; 
    document.querySelector('.menu_button').style.display = 'flex';// Zeigt den Logout-Button an

}

function checkLoginStatus() {
    if (localStorage.getItem('loggedIn')) {
        showLoggedInView();
    } else {
        document.getElementById('loginContainer').style.display = 'block';
        document.querySelector('.navigation_bar_top').style.display = 'flex';
        document.querySelector('.welcome_section').style.display = 'none';
        document.getElementById('logoutContainer').style.display = 'none'; // Versteckt den Logout-Button
        document.querySelector('.menu_button').style.display = 'none';
    }
}

