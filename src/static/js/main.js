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

    // Formulario de contacto
    const contactForm = document.getElementById('contact-form');
    const contactNote = document.getElementById('contact-form-note');

    contactForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const formData = new FormData(contactForm);
        const payload = {
            nombre: formData.get('nombre'),
            email: formData.get('email'),
            empresa: formData.get('empresa') || null,
        };

        try {
            const response = await fetch('/api/leads', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error('Request failed');
            }

            contactNote.textContent = '¡Gracias! Te contactaremos a la brevedad para coordinar tu auditoría gratuita.';
            contactForm.reset();
        } catch (error) {
            contactNote.textContent = 'Ocurrió un error al enviar el formulario. Por favor, intentá nuevamente.';
        }
    });
});
