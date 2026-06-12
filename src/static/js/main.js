document.addEventListener('DOMContentLoaded', () => {
    // Calculadora de ROI
    const calculateBtn = document.getElementById('roi-calculate');
    const hoursInput = document.getElementById('roi-hours');
    const peopleInput = document.getElementById('roi-people');
    const rateInput = document.getElementById('roi-rate');
    const resultValue = document.getElementById('roi-value');
    const resultSub = document.getElementById('roi-sub');

    calculateBtn.addEventListener('click', () => {
        const hours = parseFloat(hoursInput.value) || 0;
        const people = parseFloat(peopleInput.value) || 0;
        const rate = parseFloat(rateInput.value) || 0;

        const weeklySavings = hours * people * rate;
        const monthlySavings = weeklySavings * 4;

        resultValue.textContent = `$${monthlySavings.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
        resultSub.textContent = `Equivalente a ${(hours * people * 4).toLocaleString('en-US')} horas/mes liberadas para tu equipo`;
    });

    // Formulario de contacto (placeholder)
    const contactForm = document.getElementById('contact-form');
    const contactNote = document.getElementById('contact-form-note');

    contactForm.addEventListener('submit', (event) => {
        event.preventDefault();
        contactNote.textContent = '¡Gracias! Te contactaremos a la brevedad para coordinar tu auditoría gratuita.';
        contactForm.reset();
    });
});
